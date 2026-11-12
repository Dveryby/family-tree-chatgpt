# GEDCOM: soukromý import tvrzení a plán dokladů

## Účel a hranice

`scripts/gedcom.py` převádí textový GEDCOM do čitelného JSONu a vytvoří plán
událostí, kterým chybí pramen. Import neověřuje správnost stromu, neslučuje
osoby a nemění `research.json`. Všechna importovaná data mají stav
`unverified_claims`; jednotlivé osoby, rodiny a události `unverified`.

Implementace vychází z veřejné syntaxe FamilySearch GEDCOM. Podporuje běžné
lineage-linked soubory 5.5/5.5.1 i základní struktury verze 7. Neznámé tagy a
uživatelská rozšíření zachovává v `extensions` nebo `other_records`, ale
nepřisuzuje jim neznámý význam.

- aktuální a starší specifikace: https://gedcom.io/specs/
- GEDCOM 5.5.1: https://gedcom.io/specifications/ged551.pdf

## Použití

Vstup i výstup ulož mimo Git do soukromého úložiště:

```sh
python3 scripts/gedcom.py /soukroma/rodina.ged /soukroma/rodina-import.json
```

Je-li známé GEDCOM ID výchozí osoby, lze současně vytvořit soukromou frontu
předků:

```sh
python3 scripts/gedcom.py /soukroma/rodina.ged /soukroma/rodina-import.json --root '@I1@' --max-generations 12
```

`ancestor_research.positions` používá Kekulého číslování (1 výchozí osoba,
2 otec, 3 matka). Nástroj jako pracovní kotvu upřednostní tvrzené úmrtí či
pohřeb, potom sňatek a narození/křest s místem. Jde pouze o pořadí ověřování,
nikoli potvrzení osoby, vztahu, data nebo místa. Při více `FAMC` rodinách bez
rozlišení typu rodičovství větev automaticky nevybere; zapíše varování.

Výstup nesmí existovat; nástroj jej nepřepíše. Uloží jej s oprávněním `0600`
a vypíše pouze počty osob, rodin, pramenů, varování a položek plánu. Jména ani
další rodinné údaje do konzolového souhrnu nevypisuje.

Podporované vstupní kódování je UTF-8, ASCII a Unicode s BOM. ANSEL není v této
verzi implementovaný; takový soubor znovu exportuj z genealogického programu
jako UTF-8. Maximální velikost vstupu je 50 MiB.

## Výstup

JSON obsahuje:

- `source`: název souboru, SHA-256, deklarovanou verzi a kódování;
- `persons`: jména, pohlaví, rodinné odkazy, události, citace a rozšíření;
- `families`: partnery, děti, rodinné události a citace;
- `sources`: přenesené GEDCOM záznamy pramenů;
- `warnings`: chybějící či neplatné křížové odkazy a neobvyklé hodnoty;
- `research_plan`: chybějící narození/křty a události bez použitelné citace;
- volitelný `ancestor_research`: Kekulého pozice, pracovní kotvy, cykly a
  opakované pozice při vývodu předků; všechny se stavem neověřených tvrzení;
- `other_records`: ostatní vrcholové záznamy beze ztráty jejich struktury.

`SOUR` znamená pouze to, že autor GEDCOM připojil citaci. Není důkazem, že byl
pramen vizuálně zkontrolovaný nebo že citace podporuje konkrétní tvrzení.
Položky plánu proto převáděj do ověřených záznamů až po práci s originálním
pramenem podle hlavního postupu.

## Bezpečnost a omezení

- Import nevykonává obsah GEDCOMu a nemá síťový přístup.
- Duplicitní identifikátory, porušená hierarchie a neplatná syntaxe import zastaví.
- Chybějící odkazy na osoby, rodiny či prameny se zachovají a uvedou ve varování.
- Vstup se nemění; výstup vzniká atomicky a bez přepsání existujícího souboru.
- Import nenahrazuje úplný genealogický databázový program ani validátor všech
  sémantických pravidel GEDCOM 5.5.1/7.
