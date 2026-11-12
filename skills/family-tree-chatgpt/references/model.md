# Obecný genealogický model (formát 2)

## Proč je model oddělený

`research.json` formátu 2 rozlišuje pracovní osoby, vztahy, tvrzení, prameny
a konflikty. Samotná existence osoby nebo vztahu není důkaz. Dokazovaný obsah
patří do samostatného tvrzení s citacemi; rozporná tvrzení se uchovávají vedle
sebe a spojují konfliktem.

Původní `records` zůstávají určeny pro přepis a vizuální kontrolu archivních
zápisů. Obecný model je nenahrazuje. Pramen může přes `record_ids` odkázat na
jeden či více takových zápisů.

## Struktura stavu

Vedle `revision`, `records`, `events` a `next_step` obsahuje formát 2 mapy:

| Kolekce | Význam |
|---|---|
| `persons` | Pracovní identity osob; popisek není genealogické tvrzení |
| `relationships` | Struktura vztahu a role účastníků; pravdivost dokládají tvrzení |
| `claims` | Jedna konkrétní dokazovatelná hodnota nebo vazba |
| `sources` | Pramen s citací, soubory a případným odkazem na přečtený zápis |
| `conflicts` | Nejméně dvě tvrzení, která nelze současně přijmout bez vysvětlení |

ID všech objektů jsou stabilní: 1–96 malých ASCII písmen, číslic, pomlček nebo
podtržítek. Přejmenování ID se nepovažuje za běžnou opravu, protože na něj mohou
odkazovat další objekty.

### Osoba

```json
{
  "id": "person_synthetic_child",
  "label": "Synthetic Child",
  "notes": "Pracovní identita; popisek není důkaz jména.",
  "extensions": {}
}
```

### Vztah

```json
{
  "id": "relationship_synthetic_parent_child",
  "type": "parent_child",
  "participants": [
    {"person_id": "person_synthetic_parent", "role": "parent"},
    {"person_id": "person_synthetic_child", "role": "child"}
  ],
  "notes": "",
  "extensions": {}
}
```

Typ a role jsou otevřené textové hodnoty, aby model nevnucoval pouze biologické
rodičovství nebo manželství. Význam musí být přesný a konzistentní. Tvrzení se
subjektem tohoto vztahu určuje, zda je vazba pouze převzatá, podpořená, nebo
odmítnutá.

### Pramen

```json
{
  "id": "source_synthetic_register",
  "kind": "archive_register",
  "title": "Synthetic register",
  "citation": "Synthetic archive, collection TEST, register 1, folio 2.",
  "repository": "Synthetic archive",
  "url": "https://example.invalid/register/1",
  "accessed_on": "2026-11-12",
  "files": [
    {"path": "sources/synthetic.png", "sha256": "0000000000000000000000000000000000000000000000000000000000000000"}
  ],
  "record_ids": ["synthetic_record_001"],
  "notes": "",
  "extensions": {}
}
```

Soubor musí ležet uvnitř soukromé pracovní složky. `check` ověřuje jeho
existenci a SHA-256. `record_ids` smějí odkazovat pouze na existující položky
`records`.

### Tvrzení

```json
{
  "id": "claim_synthetic_birth_date",
  "subject": {"type": "person", "id": "person_synthetic_child"},
  "predicate": "birth.date",
  "value": "1900-01-01",
  "status": "supported",
  "citations": [
    {
      "source_id": "source_synthetic_register",
      "locator": "folio 2, entry 3",
      "quotation": "",
      "note": "Datum bylo odečteno ze samostatného sloupce."
    }
  ],
  "rationale": "Citovaný zápis datum uvádí přímo.",
  "notes": "",
  "extensions": {}
}
```

`subject.type` je `person` nebo `relationship`. `predicate` je malé stabilní
ASCII jméno, například `name.birth`, `birth.date`, `occupation` nebo
`relationship.parent_child`. `value` je libovolná konečná JSON hodnota.

Stavy tvrzení:

- `unverified`: převzaté nebo dosud neposouzené tvrzení;
- `supported`: podpořené uvedenými prameny a zdůvodněním;
- `rejected`: prameny a zdůvodnění podporují jeho odmítnutí.

`supported` a `rejected` vyžadují alespoň jednu citaci a neprázdné zdůvodnění.
Program kontroluje strukturu, nikoli věcnou sílu důkazu.

### Konflikt

```json
{
  "id": "conflict_synthetic_birth_date",
  "claim_ids": ["claim_birth_1900", "claim_birth_1901"],
  "status": "open",
  "resolution": {"preferred_claim_ids": [], "rationale": ""},
  "notes": "",
  "extensions": {}
}
```

Při `resolved` je povinné zdůvodnění. `preferred_claim_ids` mohou obsahovat jen
tvrzení z daného konfliktu; seznam může zůstat prázdný, jestliže byly odmítnuty
všechny varianty. Vyřešení konfliktu nemaže původní tvrzení ani citace.

## Atomická změna modelu

Příkaz `model apply` přijme JSON objekt, jehož klíče jsou názvy kolekcí a hodnoty
seznamy celých objektů. Existující objekt stejného ID se celý nahradí. Všechny
odkazy se ověří až nad výsledkem celé změny, takže lze v jednom kroku přidat
osoby, vztah, pramen i tvrzení.

```json
{
  "persons": [
    {"id": "person_a", "label": "Synthetic A", "notes": "", "extensions": {}}
  ],
  "sources": [],
  "claims": []
}
```

```sh
python3 scripts/family_tree.py --workspace /soukroma model apply /soukroma/zmena.json \
  --expected-revision 4 --next-step "Ověřit tvrzené datum v druhém prameni."
python3 scripts/family_tree.py --workspace /soukroma model show --collection persons
python3 scripts/family_tree.py --workspace /soukroma project audit
```

Změna neumožňuje mazání. Bezpečné mazání bude vyžadovat samostatný návrh, který
zohlední odkazy, historii a význam odstranění důkazu. Soukromý změnový JSON
nesmí ležet v Git repozitáři.

## Migrace formátu 1

Starý stav lze nadále číst, kontrolovat, exportovat a obnovit. Obecný model je
dostupný až po výslovné migraci s aktuální revizí:

```sh
python3 scripts/family_tree.py --workspace /soukroma project migrate \
  --expected-revision 12 --next-step "Založit první osoby a tvrzení."
```

Migrace vytvoří prázdné kolekce obecného modelu, zvýší revizi a zachová předchozí
stav v `history/`. Ze starých přepisů automaticky nevytváří osoby, vztahy ani
tvrzení; jejich význam musí badatel určit vědomě.
