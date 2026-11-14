#!/usr/bin/env python3
"""Stable offline CLI for private genealogical research."""
import argparse
import json
from pathlib import Path
import sys

import gedcom
import gramps
import research


MAX_JSON_INPUT_BYTES = 50 * 1024 * 1024


def project_version():
    candidates = (
        Path(__file__).resolve().parents[3] / "VERSION",
        Path(__file__).resolve().parents[1] / "VERSION",
    )
    for candidate in candidates:
        try:
            value = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value
    return "development"


def private_json(path):
    candidate = Path(path).expanduser()
    if candidate.is_symlink():
        raise ValueError("JSON vstup musí být běžný soubor, nikoli symlink.")
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise ValueError("JSON vstup musí být běžný soubor.")
    if research.in_git_tree(resolved):
        raise ValueError("Soukromý JSON vstup ulož mimo git repozitář.")
    if resolved.stat().st_size > MAX_JSON_INPUT_BYTES:
        raise ValueError("JSON vstup překračuje limit 50 MiB.")
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("JSON vstup není platný UTF-8 JSON.") from exc
    return value


def require_workspace(args):
    if args.workspace is None:
        raise ValueError("Tento příkaz vyžaduje --workspace před názvem příkazu.")
    return research.private_workspace(args.workspace)


def state_summary(state):
    return {
        "schema_version": state["schema_version"],
        "revision": state["revision"],
        "records": len(state["records"]),
        "persons": len(state.get("persons", {})),
        "relationships": len(state.get("relationships", {})),
        "claims": len(state.get("claims", {})),
        "sources": len(state.get("sources", {})),
        "conflicts": len(state.get("conflicts", {})),
        "next_step": state["next_step"],
    }


def gedcom_import(args):
    result = gedcom.build_import(args.gedcom)
    if args.root:
        result["ancestor_research"] = gedcom.ancestor_research(
            result, args.root, args.max_generations
        )
    output = gedcom.atomic_output(args.output, result)
    summary = {
        "imported": True,
        "output": str(output),
        "source_sha256": result["source"]["sha256"],
        "persons": len(result["persons"]),
        "families": len(result["families"]),
        "sources": len(result["sources"]),
        "warnings": len(result["warnings"]),
        "plan_items": len(result["research_plan"]),
    }
    if "ancestor_research" in result:
        summary["ancestor_positions"] = len(result["ancestor_research"]["positions"])
        summary["ancestor_warnings"] = len(result["ancestor_research"]["warnings"])
    return summary


def image_command(args):
    # Pillow is imported only for image commands. Project and GEDCOM operations
    # therefore remain usable in a standard-library-only environment.
    import crop
    import image_review

    if args.image_command == "crop":
        return crop.crop_scan(args.source, args.output, image_review.parse_box(args.box))
    if args.image_command == "split":
        return image_review.split_review(
            args.source,
            (args.output_first, args.output_second),
            image_review.parse_box(args.box),
            args.direction,
            args.overlap,
            args.contrast,
            args.width,
        )
    if args.image_command == "mark":
        return image_review.marked_preview(
            args.source, args.output, [image_review.parse_box(value) for value in args.box]
        )
    return image_review.contact_sheet(
        args.sources,
        args.output,
        image_review.parse_box(args.box),
        args.columns,
        args.width,
    )


def gramps_client(args):
    client = gramps.Client(
        args.url,
        timeout=args.timeout,
        allow_http=args.allow_http,
    )
    gramps.authenticate(
        client,
        username=args.username,
        password_env=args.password_env,
        token_env=args.token_env,
    )
    return client


def gramps_tasks_command(args):
    client = gramps_client(args)
    if args.tasks_command == "probe":
        return gramps.tasks_probe(client)
    if args.tasks_command == "push":
        plan = gramps.validate_task_plan(private_json(args.plan_json))
        return gramps.push_task_plan(client, plan)
    task_input = gramps.validate_task_input(private_json(args.tasks_json))
    plan = gramps.make_task_plan(client, task_input)
    output = gramps.write_plan(args.output, plan, research.in_git_tree)
    return gramps.task_plan_summary(plan, output)


def gramps_command(args):
    if args.gramps_command == "tasks":
        return gramps_tasks_command(args)
    client = gramps_client(args)
    if args.gramps_command == "probe":
        return gramps.probe(client)

    root = require_workspace(args)
    state = research.read_state(root)
    errors = research.check_state(state, root)
    if errors:
        raise ValueError("\n".join(errors))
    state_hash = research.sha256(root / "research.json")
    if args.gramps_command == "push":
        plan = gramps.validate_plan(private_json(args.plan_json))
        return gramps.push(client, plan, state["revision"], state_hash)

    plan = gramps.make_plan(client, state, state_hash)
    if args.gramps_command == "status":
        return gramps.status(plan)
    output = gramps.write_plan(args.output, plan, research.in_git_tree)
    return gramps.plan_summary(plan, output)


def execute(args):
    if args.command == "archive":
        import mza

        if args.mza_command == "download":
            return mza.download(args.url)
        if args.mza_command == "inspect":
            root = require_workspace(args) if args.workspace is not None else None
            return mza.inspect(args.url, root, args.file)
        return mza.import_image(
            require_workspace(args), args.file, args.url, method=args.method,
            reference=args.reference, image_number=args.image_number,
            digital_copy=args.digital_copy, provenance_note=args.provenance_note,
            acquired_at=args.acquired_at, expected_revision=args.expected_revision,
        )
    if args.command == "gedcom":
        return gedcom_import(args)
    if args.command == "image":
        return image_command(args)
    if args.command == "gramps":
        return gramps_command(args)

    root = require_workspace(args)
    if args.command == "project":
        if args.project_command == "init":
            research.initialize(root)
            result = state_summary(research.read_state(root))
            result["initialized"] = True
            result["workspace"] = str(root)
            return result
        if args.project_command == "resume":
            return research.read_state(root)
        if args.project_command == "check":
            state = research.read_state(root)
            errors = research.check_state(state, root)
            if errors:
                raise ValueError("\n".join(errors))
            return {"valid": True, **state_summary(state)}
        if args.project_command == "audit":
            state = research.read_state(root)
            errors = research.check_state(state, root)
            if errors:
                raise ValueError("\n".join(errors))
            return research.audit_state(state)
        if args.project_command == "migrate":
            state = research.migrate(root, args.expected_revision, args.next_step)
            return {"migrated": True, **state_summary(state)}
        if args.project_command == "export":
            return research.export_bundle(root, args.bundle)
        if args.project_command == "restore":
            return research.restore_bundle(root, args.bundle)
        state = research.update(
            root,
            args.expected_revision,
            result=args.result,
            scope=args.scope,
            next_step=args.next_step,
        )
        return {"logged": True, "result": args.result, **state_summary(state)}

    if args.command == "record":
        record = private_json(args.record_json)
        state = research.update(
            root,
            args.expected_revision,
            record=record,
            next_step=args.next_step,
        )
        return {"saved": True, "record_id": record.get("id"), **state_summary(state)}

    state = research.read_state(root)
    if args.model_command == "show":
        return research.model_view(state, args.collection, args.id)
    patch = private_json(args.patch_json)
    state = research.apply_model(
        root,
        args.expected_revision,
        patch,
        args.next_step,
    )
    return {"applied": True, **state_summary(state)}


def build_parser():
    parser = argparse.ArgumentParser(prog="family-tree", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {project_version()}")
    parser.add_argument("--workspace", type=Path, help="soukromá badatelská složka mimo Git")
    commands = parser.add_subparsers(dest="command", required=True)

    archive = commands.add_parser("archive", help="import a místní kontrola archivních snímků")
    archives = archive.add_subparsers(dest="archive_name", required=True)
    mza_parser = archives.add_parser("mza", help="MZA: import bez sítě, živé stahování zakázáno")
    mza_commands = mza_parser.add_subparsers(dest="mza_command", required=True)
    mza_import = mza_commands.add_parser("import", help="nezměněná kopie snímku do sources/")
    mza_import.add_argument("file", type=Path)
    mza_import.add_argument("--url", required=True)
    mza_import.add_argument(
        "--method", default="manual_import",
        choices=("browser_download", "archival_copy", "iiif_assembled", "screenshot", "manual_import"),
    )
    mza_import.add_argument("--reference", default="", help="skutečně doložená identifikace matriky")
    mza_import.add_argument("--image-number", type=int, help="ověřené pořadové číslo snímku")
    mza_import.add_argument("--digital-copy", choices=("unknown", "derived", "original"), default="unknown")
    mza_import.add_argument("--provenance-note", default="", help="podklad pro označení originální digitální kopie")
    mza_import.add_argument("--acquired-at", help="ISO čas získání s časovým pásmem; jinak čas importu")
    mza_import.add_argument("--expected-revision", type=int)
    mza_inspect = mza_commands.add_parser("inspect", help="místní metadata a duplicity, žádná síť")
    mza_inspect.add_argument("--url", required=True)
    mza_inspect.add_argument("--file", type=Path, help="volitelně porovnat SHA-256 místního souboru")
    mza_download = mza_commands.add_parser("download", help="v této verzi vždy odmítne síťový přístup")
    mza_download.add_argument("--url", required=True)

    project = commands.add_parser("project", help="životní cyklus badatelského projektu")
    project_commands = project.add_subparsers(dest="project_command", required=True)
    for name in ("init", "resume", "check", "audit"):
        project_commands.add_parser(name)
    migrate = project_commands.add_parser("migrate", help="výslovně převést formát 1 na formát 2")
    migrate.add_argument("--expected-revision", required=True, type=int)
    migrate.add_argument("--next-step", required=True)
    export = project_commands.add_parser("export")
    export.add_argument("bundle", type=Path)
    restore = project_commands.add_parser("restore")
    restore.add_argument("bundle", type=Path)
    log = project_commands.add_parser("log")
    log.add_argument("--result", required=True, choices=("not_found", "blocked", "note"))
    log.add_argument("--scope", required=True)
    log.add_argument("--expected-revision", required=True, type=int)
    log.add_argument("--next-step", required=True)

    record = commands.add_parser("record", help="archivní zápisy a jejich čtení")
    record_commands = record.add_subparsers(dest="record_command", required=True)
    put = record_commands.add_parser("put")
    put.add_argument("record_json", type=Path)
    put.add_argument("--expected-revision", required=True, type=int)
    put.add_argument("--next-step", required=True)

    model = commands.add_parser("model", help="osoby, vztahy, tvrzení, prameny a konflikty")
    model_commands = model.add_subparsers(dest="model_command", required=True)
    apply = model_commands.add_parser("apply", help="atomicky vložit nebo nahradit objekty podle ID")
    apply.add_argument("patch_json", type=Path)
    apply.add_argument("--expected-revision", required=True, type=int)
    apply.add_argument("--next-step", required=True)
    show = model_commands.add_parser("show", help="zobrazit obecný model nebo jeho část")
    show.add_argument("--collection", choices=research.MODEL_COLLECTIONS)
    show.add_argument("--id")

    gramps_parser = commands.add_parser(
        "gramps", help="bezpečné append-only propojení s Gramps Web API"
    )
    gramps_commands = gramps_parser.add_subparsers(dest="gramps_command", required=True)

    def add_gramps_connection(command):
        command.add_argument("--url", required=True, help="základní URL instance Gramps Web")
        command.add_argument("--username", help="uživatel; heslo se neuvádí na příkazové řádce")
        command.add_argument("--password-env", default="GRAMPS_WEB_PASSWORD")
        command.add_argument("--token-env", default="GRAMPS_WEB_TOKEN")
        command.add_argument("--timeout", type=float, default=20)
        command.add_argument(
            "--allow-http",
            action="store_true",
            help="povolit nešifrované HTTP pouze pro izolovaný lokální test",
        )

    probe = gramps_commands.add_parser("probe", help="ověřit spojení a kompatibilitu bez zápisu")
    add_gramps_connection(probe)
    plan = gramps_commands.add_parser("plan", help="vytvořit soukromý append-only plán")
    plan.add_argument("output", type=Path)
    add_gramps_connection(plan)
    push = gramps_commands.add_parser("push", help="provést beze změn uložený plán")
    push.add_argument("plan_json", type=Path)
    add_gramps_connection(push)
    status = gramps_commands.add_parser("status", help="porovnat podporovaná tvrzení se serverem")
    add_gramps_connection(status)

    tasks = gramps_commands.add_parser(
        "tasks", help="vytvářet standardní soukromé úkoly Gramps Web"
    )
    task_commands = tasks.add_subparsers(dest="tasks_command", required=True)
    task_probe = task_commands.add_parser(
        "probe", help="ověřit podporu úkolů a stav tagu ToDo bez zápisu"
    )
    add_gramps_connection(task_probe)
    task_plan = task_commands.add_parser(
        "plan", help="připravit append-only plán z explicitního JSON seznamu úkolů"
    )
    task_plan.add_argument("tasks_json", type=Path)
    task_plan.add_argument("output", type=Path)
    add_gramps_connection(task_plan)
    task_push = task_commands.add_parser(
        "push", help="vytvořit úkoly podle nezměněného soukromého plánu"
    )
    task_push.add_argument("plan_json", type=Path)
    add_gramps_connection(task_push)

    gedcom_parser = commands.add_parser("gedcom", help="bezpečný offline import GEDCOM tvrzení")
    gedcom_commands = gedcom_parser.add_subparsers(dest="gedcom_command", required=True)
    gedcom_import_parser = gedcom_commands.add_parser("import")
    gedcom_import_parser.add_argument("gedcom", type=Path)
    gedcom_import_parser.add_argument("output", type=Path)
    gedcom_import_parser.add_argument("--root")
    gedcom_import_parser.add_argument("--max-generations", type=int, default=12)

    image = commands.add_parser("image", help="místní obrazové deriváty bez sítě")
    image_commands = image.add_subparsers(dest="image_command", required=True)
    image_crop = image_commands.add_parser("crop")
    image_crop.add_argument("source", type=Path)
    image_crop.add_argument("output", type=Path)
    image_crop.add_argument("--box", required=True)
    split = image_commands.add_parser("split")
    split.add_argument("source", type=Path)
    split.add_argument("output_first", type=Path)
    split.add_argument("output_second", type=Path)
    split.add_argument("--box", default="0,0,1,1")
    split.add_argument("--direction", choices=("left-right", "top-bottom"), default="left-right")
    split.add_argument("--overlap", type=float, default=0.04)
    split.add_argument("--contrast", action="store_true")
    split.add_argument("--width", type=int, default=1900)
    mark = image_commands.add_parser("mark")
    mark.add_argument("source", type=Path)
    mark.add_argument("output", type=Path)
    mark.add_argument("--box", action="append", required=True)
    sheet = image_commands.add_parser("sheet")
    sheet.add_argument("output", type=Path)
    sheet.add_argument("sources", nargs="+", type=Path)
    sheet.add_argument("--box", default="0,0,1,0.15")
    sheet.add_argument("--columns", type=int, default=1)
    sheet.add_argument("--width", type=int, default=1200)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "model" and args.model_command == "show" and args.id and not args.collection:
            raise ValueError("--id vyžaduje také --collection.")
        print(json.dumps(execute(args), ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
