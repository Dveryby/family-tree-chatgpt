# ETAPA 2: importní adaptéry `research.json`

## Rozsah a bezpečnost

ETAPA 2 importuje platný `research.json` schématu 1 nebo 2 do existující
SQLite databáze. Vstupem je soukromá pracovní složka nebo její soubor
`research.json`; vstup ani média se nemění. Import je místní a nemá síťový
klient.

Každá datová historie má vlastní `import_branches`. Relační primární klíče jsou
deterministicky jmenně oddělené podle větve a původní ID jsou beze změny v
`source_identifier`. Adaptér osoby ani prameny mezi větvemi neslučuje a
neprovádí posouzení totožnosti.

Bezeztrátová vrstva uchovává:

- aktuální JSON a dostupné `history/revision-*.json` jako neměnné snapshoty;
- původní JSON každé osoby, vazby, tvrzení, citace, pramene, záznamu a konfliktu;
- přepis, překlad a interpretaci odděleně, bez domyšleného autorství;
- nejistoty, historii událostí, odkazy na soubory, SHA-256 a obrazovou provenienci;
- všechny běžné soubory v `sources/` a `crops/`, i když je aktuální stav přímo
  neodkazuje.

Archiv B nebyl pro vývoj lokálně dostupný. Automatické testy proto používají
výslovně syntetický formát-1 fixture `tests/fixtures/research_v1_synthetic.json`;
neobsahuje rodinná data ani archivní snímky.

Otevřené konflikty se importují jako otevřené. Kódy rozpoznané z ID `k01` až
`k13` se v reportu zobrazí jako `K01` až `K13`; žádná varianta se automaticky
nevybírá.

## Import a dry-run

Databáze musí být před importem na aktuální verzi migrací:

```sh
python3 skills/family-tree-chatgpt/scripts/family_tree.py \
  database migrate /soukrome/family-tree-2.sqlite

python3 skills/family-tree-chatgpt/scripts/family_tree.py \
  database import-research /soukrome/family-tree-2.sqlite /soukrome/vetev-a \
  --project-id rodokmen --project-name "Soukromý výzkum" \
  --branch-key revision_13_a --branch-label "Revize 13 – větev A" \
  --actor badatel --dry-run
```

Po kontrole reportu se stejný příkaz spustí bez `--dry-run`. Idempotency klíč
obsahuje SHA-256 aktuálního `research.json` a verzi adaptéru. Opakování stejného
importu nic nepřidá. Změněný `research.json` se importuje pod novým `branch_key`;
adaptér odmítne přepsat již naplněnou větev.

Report uvádí verzi a revizi vstupu, SHA-256, počty zdrojových a vložených
objektů, otevřené konflikty, normalizace a varování. U tvrzení se zdrojovým
stavem `supported` nebo `rejected` a platnou citací a zdůvodněním používá SQLite
nejnižší nenulovou úroveň `lead`; původní celé tvrzení zůstává v `source_json`
a normalizace je výslovně uvedena v reportu.

## Lokální schválení Gramps outboxu

Schvalovací JSON zůstává mimo Git:

```json
{
  "schema_version": 1,
  "project_id": "rodokmen",
  "operations": [
    {
      "branch_key": "revision_13_a",
      "idempotency_key": "gramps:create:person:person_a",
      "operation_type": "create_person",
      "aggregate_type": "person",
      "aggregate_id": "person_a",
      "claim_ids": ["claim_supported_name"],
      "payload": {"handle": "private-deterministic-handle"}
    }
  ]
}
```

```sh
python3 skills/family-tree-chatgpt/scripts/family_tree.py \
  database outbox-approve /soukrome/family-tree-2.sqlite /soukrome/outbox.json \
  --approved-by badatel --dry-run
```

Bez `--dry-run` se způsobilé položky pouze vloží do neměnného lokálního
`sync_outbox`. Každá operace musí odkazovat na `supported` tvrzení mimo otevřený
konflikt; u vyřešeného konfliktu musí jít o preferovanou variantu. Příkaz
uloží s payloadem i `branch_key` a původní ID schválených tvrzení, nevytváří
`sync_outbox_attempts`, neobsahuje odesílač a nic do Gramps Web neodesílá.
