# Family Tree MCP 2.1 — kontrakt k 17. 11. 2026

Nejprve ověř aktuální sadu dostupných MCP nástrojů. Instalace tohoto skills-only
pluginu sama o sobě **nepřipojuje** vlastní Family Tree MCP server.

## Čtení

`database_status` poskytuje počty a seznam větví, **nikoli** nejnovější auditní
revizi a hash. Pro audit použij `list_audit_revisions` a `get_audit_revision`
se skutečným `project_id`. `search_persons`, `search_records`, `get_record`,
`get_claim` slouží k dohledání přesných objektů. `get_media_info` a `get_media`
přinášejí metadata a původní PNG s kontrolou integrity podle `media_id`.

## Atomické uložení

`research_save_findings` přijímá:
- povinné `branch_key` (explicitně `rev13_a` nebo `rev13_b`),
  `idempotency_key`, `source`, `record`, `claims`;
- volitelně `persons`, `transcription`, `translation`, `interpretation`,
  `uncertainties`, `locator`, `preview_only` (výchozí `true`).

Pro existující zdroj a zápis použij slovník `{"id":"skutecne-id"}`. U nových
osob zadej identitní kontejnery explicitně; nic neslučuj podle jména.
U tvrzení se `subject_kind="record"` nezadávej `subject_id`; vychází
z `record`. Zajisti citace a lokátory v rozsahu skutečných pramenů.

Na pokyn uložit je po kontrole parametrů možné `preview_only=false`. Operace
ukládá zdroj, zápis, citace, tvrzení a případné texty v jedné transakci.
Tvrzení vznikají jako `unverified`, nikoli automaticky `supported`.
Pro doplnění/nové rozhodnutí použij nový `idempotency_key` a zachovej historii.
Po uložení ověř přesná ID a audit. Nejasná síťová chyba není povolení k
nekontrolovanému opakování.

Původní `prepare_claim_write` a `commit_claim_write` jsou dostupná starší
rozhraní pro jednotlivé zápisy a mají vlastní schvalovací tok.

## Gramps

`gramps_status`, `gramps_list_trees`, `gramps_find`, `gramps_get` čtou
stav cílového stromu. `gramps_publish_person` vytváří jednu osobu, případně
vazbu na existující rodiče, na základě `external_id`, jména, příjmení,
zdrojového popisu a aspoň jedné životní události. Podporuje `preview_only`.
Při explicitním publikačním pokynu a odpovídající nejistotě smí jít do Gramps
i pracovní hypotéza. Nesmí se však doplňovat neznámé datum kvůli validaci.

`gramps_prepare_write` a `gramps_commit_write` umožňují jiné cílené
objektové operace v odděleném schvalovacím toku. Neexistuje potvrzený nástroj
`research_publish_to_gramps`: automatické batch mapování SQLite → Gramps,
tagy jistoty, citace a konflikty se nesmí předstírat. Po každém zápisu
ověř výsledné ID a rodinné vazby; při nejasné odpovědi nejdřív čti, pak případně
opakuj.

## Důkazní stavy

MCP SQLite rozlišuje `claims.status = unverified | supported | rejected` a
oddělený `evidence_level`. Badatelské DOLOŽENO / PRAVDĚPODOBNÉ / HYPOTÉZA /
NEVYŘEŠENO je interpretační klasifikace, nikoli mechanické mapování na
SQLite statusy. Otevřené rozpory ponech vedle sebe; nevyráběj definitivní
výsledek pouze proto, aby měl Gramps pole vyplněno.
