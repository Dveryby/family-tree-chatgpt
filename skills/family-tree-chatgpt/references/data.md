# Soukromý badatelský stav (formát 1)

## Prostředí a nástroje

- Python 3.11+; `research.py` používá standardní knihovnu.
- `crop.py` potřebuje Pillow. Závislost nejprve ověřit v existujícím prostředí.
- Příklady volají skripty ze složky balíčku. Skutečné cesty odvodit ze složky načteného skillu.
- Skripty nemají síťový přístup ani trvalé cloudové ukládání.

## Soubory

Soukromá složka je mimo git repozitáře. Obsahuje `research.json`, `sources/`,
`crops/`, `history/`. Soubor `.research.lock` existuje během zápisu.
Zámek po pádu procesu nerušit bez ověření, že jiný zápis neběží.
Podpora je pro jednoho lokálního zapisovatele; cloudovou synchronizaci a konflikty
na více zařízeních musí řešit úložiště před příkazem `put` či `log`.

`research.json` obsahuje `schema_version: 1`, celočíselnou `revision`, mapu `records`,
seznam `events` a text `next_step`. Jeden zápis, událost a další krok se ukládají
jednou atomickou náhradou souboru. `history/` uchovává předchozí revize;
nejde o vzdálenou zálohu ani nezměnitelný auditní systém.

## Přenosový balíček

`export` nejprve ověří stav a kontrolní součty, zamkne pracovní složku proti
souběžnému zápisu a vytvoří ZIP atomicky bez přepsání existujícího výstupu.
Zahrne pouze `research.json`, pravidelné soubory v `sources/`, `crops/` a
`history/` a vnitřní `manifest.json`. Manifest obsahuje verzi formátu, revizi,
čas vytvoření, velikost a SHA-256 každého souboru. `.research.lock`, pomocné
soubory v kořeni, symlinky a přístupové údaje se nepřenášejí.

```sh
python scripts/research.py --workspace /soukroma export /uloziste/badani-r12.zip
```

Výstupní ZIP musí ležet mimo badatelskou složku i git repozitář. Skript ZIP
nešifruje ani nenahrává; soukromí, přístupová práva, verzování a dostupnost
zajišťuje zvolené úložiště. Vrácený `bundle_sha256` uložit spolu s identifikací
verze balíčku.

`restore` přijímá pouze podporovaný manifest, deklarované pravidelné soubory a
bezpečné relativní cesty. Ověří velikosti, SHA-256, revizi a celý obnovený stav.
Odmítne symlinky, duplicitní či nadbytečné položky, cestu mimo cíl, změněný
obsah a existující cílovou složku. Rozbalování probíhá v dočasné složce; při
chybě se neúplný cíl nezachová.

```sh
python scripts/research.py --workspace /nova/soukroma restore /uloziste/badani-r12.zip
python scripts/research.py --workspace /nova/soukroma check
python scripts/research.py --workspace /nova/soukroma resume
```

Po obnově porovnat revizi, `next_step`, počet záznamů a SHA-256 balíčku. Teprve
pak pokračovat příkazy `put` nebo `log` s aktuální očekávanou revizí.

## Jeden záznam

Kostru má `assets/record.json`. ID je stabilní ASCII identifikátor, např.
`synthetic_birth_1900_001`. `put` nahrazuje celý jeden záznam stejného ID.
Ostatní záznamy se nezmění. Před úpravou načíst uloženou verzi.

| Pole | Význam |
|---|---|
| `source.archive` | Archiv nebo přesný původ dodaného snímku |
| `source.reference` | Fond/sbírka a signatura knihy |
| `source.page` | Strana/folio a číslo snímku, rozlišené |
| `source.url` | Přesný zjištěný odkaz, jinak prázdný text |
| `source.accessed_on` | Datum prohlédnutí YYYY-MM-DD, jinak prázdný text |
| `source.file`, `source.crop` | Relativní cesty uvnitř soukromé složky |
| `source.file_sha256`, `source.crop_sha256` | Kontrolní součty doplněné při uložení |
| `reading_status` | `unread`, `draft`, `reviewed` |
| `visual_review` | Skutečně proběhla vizuální kontrola? |
| `transcription` | Původní znění včetně nejasností |
| `translation` | Český překlad |
| `interpretation` | Výklad, důsledky a rozpory |
| `uncertainties` | Seznam otevřených čtení a otázek |
| `identity.status` | `unresolved`, `supported`, `rejected` |
| `identity.rationale` | Odůvodnění posouzení totožnosti |
| `identity.evidence` | Citace podkladů pro totožnost jako seznam textů |

`reviewed` vyžaduje úplnou citaci, existující originál i výřez, přepis a
`visual_review: true`. Při chybějící citaci lze uložit `draft`.
Stav je oddělený od totožnosti. I částečně nečitelný zápis může být vizuálně
zkontrolovaný: ponechat výslovné nejistoty. `supported` a `rejected` vyžadují
odůvodnění a citace; program kontroluje přítomnost, nikoli věcnou správnost.

## Výřez

```sh
python scripts/crop.py /soukroma/sources/scan.png /soukroma/crops/record.png --box 0.1,0.2,0.9,0.6
```

Výstup je PNG bez EXIF/GPS; originál zůstává beze změny. Souřadnice jsou po EXIF
orientaci. Nástroj nezvětšuje, nedoostřuje a nepřepisuje existující výřez.
Vrací JSON se souřadnicemi a součty; lze jej uložit do doplňkového pole `crop_metadata`.
Pro čtení vždy skutečně prohlédnout obrázek.

## Kontrolní obrázky

Funkce adaptované z původních nástrojů `overit.py`, `ramecek.py` a místního
režimu `mapa_knihy.py` jsou sloučené v jednom offline skriptu:

```sh
python scripts/image_review.py split /soukroma/sources/scan.png /soukroma/crops/left.png /soukroma/crops/right.png --box 0.1,0.2,0.9,0.6
python scripts/image_review.py mark /soukroma/crops/record.png /soukroma/crops/record-marked.png --box 0.05,0.1,0.95,0.8
python scripts/image_review.py sheet /soukroma/crops/book-map.png /soukroma/sources/scan-10.png /soukroma/sources/scan-20.png --box 0,0,1,0.15
```

`split` zachová překryv mezi částmi; `--contrast` vytvoří pracovní černobílou
kopii. `mark` zakreslí jeden či více rámečků (`--box` lze opakovat). `sheet`
slepí stejné oblasti již uložených snímků a nestahuje nic ze sítě. Vstupy musí
být běžné soubory, výstupy nové soukromé PNG mimo Git. Skript vrací SHA-256 a
původní soubory nemění.

## Kontrola a pokračování

```sh
python scripts/research.py --workspace /soukroma resume
python scripts/research.py --workspace /soukroma put /soukroma/zaznam.json --expected-revision 0 --next-step "Ověřit druhého stejnojmenného kandidáta."
python scripts/research.py --workspace /soukroma check
python scripts/research.py --workspace /soukroma audit
python scripts/research.py --workspace /soukroma log --result not_found --scope "Konkrétní kniha, snímky 12–16, hledané jméno" --expected-revision 1 --next-step "Projít rejstřík sňatků."
```

Revize jsou příklady, vždy načíst aktuální hodnotu.
`check` blokuje poškozený nebo nedoložený stav. `audit` je pouze čtecí kontrola
kvality: vypíše počty stavů a upozornění, která je nutné věcně posoudit.
