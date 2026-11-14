# Soukromý badatelský stav (formát 2)

## Prostředí a nástroje

- Python 3.11+; `research.py` používá standardní knihovnu.
- Obrazové příkazy potřebují Pillow. Závislost nejprve ověřit v existujícím prostředí.
- Příklady volají skripty ze složky balíčku. Skutečné cesty odvodit ze složky načteného skillu.
- Projektové, modelové, GEDCOM a obrazové příkazy zůstávají offline. Pouze
  skupina `gramps` používá síť podle [samostatné reference](gramps.md);
  žádný příkaz neprovádí trvalé cloudové ukládání badatelského ZIPu.
- `archive mza import/inspect` zůstávají offline. Pouze výslovný `download`
  používá síť se soukromě evidovaným souhlasem podle [reference MZA](mza.md).
- Stabilní vstup je `scripts/family_tree.py`. Samostatné `research.py`,
  `gedcom.py`, `crop.py` a `image_review.py` zůstávají kvůli kompatibilitě,
  ale nové postupy mají používat jednotné CLI.

## Soubory

Soukromá složka je mimo git repozitáře. Obsahuje `research.json`, `sources/`,
`crops/`, `history/`. Soubor `.research.lock` existuje během zápisu.
Zámek po pádu procesu nerušit bez ověření, že jiný zápis neběží.
Podpora je pro jednoho lokálního zapisovatele; cloudovou synchronizaci a konflikty
na více zařízeních musí řešit úložiště před příkazem `put` či `log`.

`research.json` obsahuje `schema_version: 2`, celočíselnou `revision`, mapu `records`,
obecný model osob, vztahů, tvrzení, pramenů a konfliktů, seznam `events` a text
`next_step`. Podrobné schéma je v [referenci modelu](model.md). Jedna změna a
další krok se ukládají atomickou náhradou souboru. `history/` uchovává předchozí revize;
nejde o vzdálenou zálohu ani nezměnitelný auditní systém.

Formát 1 lze dál kontrolovat, exportovat a obnovit. Před prvním použitím
obecného modelu jej převést výslovným `project migrate`; automatická migrace
osob nebo příbuzenských vazeb se neprovádí.

## Přenosový balíček

`export` nejprve ověří stav a kontrolní součty, zamkne pracovní složku proti
souběžnému zápisu a vytvoří ZIP atomicky bez přepsání existujícího výstupu.
Zahrne pouze `research.json`, pravidelné soubory v `sources/`, `crops/` a
`history/` a vnitřní `manifest.json`. Manifest obsahuje verzi formátu, revizi,
čas vytvoření, velikost a SHA-256 každého souboru. `.research.lock`, pomocné
soubory v kořeni, symlinky a přístupové údaje se nepřenášejí.

```sh
python3 scripts/family_tree.py --workspace /soukroma project export /uloziste/badani-r12.zip
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
python3 scripts/family_tree.py --workspace /nova/soukroma project restore /uloziste/badani-r12.zip
python3 scripts/family_tree.py --workspace /nova/soukroma project check
python3 scripts/family_tree.py --workspace /nova/soukroma project resume
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

## Metadata importovaného snímku MZA

`archive mza import` založí běžný záznam s ID `mza_` a SHA-256 kombinace přesné
URL a hashe souboru. Nevytváří osoby, vztahy ani tvrzení. `reading_status`
zůstává `unread`, `visual_review` je `false`, totožnost `unresolved`.
`source.file` ukazuje do `sources/mza-<SHA-256>.<skutečný-formát>`;
`source.file_sha256` ověřuje nezměněné bajty. Přípona vstupu se nepovažuje
za důkaz formátu. Nové nepovinné pole `source.acquisition` obsahuje:

| Pole | Význam |
| --- | --- |
| `schema_version` | Verze metadat získání, nyní `1` |
| `url`, `archive`, `reference` | Skutečná URL, název archivu, známá identifikace knihy; shodné se `source` |
| `image_number` | Ověřené pořadové číslo, jinak `null`; neodvozuje se z názvu JP2 |
| `acquired_at`, `imported_at` | ISO časy s časovým pásmem; bez dodaného času získání je použit čas převzetí při importu |
| `method` | `browser_download`, `archival_copy`, `iiif_assembled`, `screenshot`, `manual_import` |
| `digital_copy` | `derived`, `original`, `unknown`; `original` vyžaduje archivní kopii s podkladem |
| `provenance_note` | Podklad pro původ digitální kopie, jinak prázdný text |
| `format`, `width`, `height` | Skutečný formát Pillow a nezměněné pixelové rozměry |
| `size_bytes`, `sha256` | Délka a SHA-256 uložených bajtů |

Neznámá signatura zůstává prázdným textem. `browser_download`, `screenshot`
a `iiif_assembled` jsou odvozené soubory bez ohledu na vstupní příponu.
Stejné bajty s jinou URL zachovají samostatný záznam původu a společný soubor;
stejná URL s jinými bajty vytvoří další záznam. Shodný import vrátí
`duplicate: true`, nezvyšuje revizi a nemění již uložené čtení. Při rozdílných
metadatech téhož importu skončí chybou; změnu je nutné věcně provést `record put`.

Metadata jsou součástí atomicky ukládaného `research.json` a historie.
Zápis probíhá pod existujícím zámkem; soubor se nejprve zkopíruje a úplně
ověří v dočasném umístění, potom atomicky zveřejní bez přepsání. Selhání zápisu
stavu uklidí právě vytvořenou kopii; dříve existující soubory zachová. Pád procesu
mezi zveřejněním souboru a uložením JSON může zanechat osiřelou úplnou kopii,
nikoli úspěšný záznam; po ověření zámku lze import bezpečně zopakovat.
`project check` kontroluje strukturu původu, shodu SHA-256 a velikost;
`archive mza inspect` navíc skutečně dekóduje vybraný snímek a porovná rozměry
a formát. Kontroly neposuzují správnost citace nebo pravost archivní kopie.

Export zahrne metadata v JSON, historii a soubory v `sources/` pomocí stávajícího
manifestu se SHA-256. Obnova pokračuje stejnou revizí. Starší záznamy bez
`acquisition` zůstávají platné; nemění se verze badatelského stavu ani ZIPu.
Import funguje také ve formátu 1, bez automatické migrace. Při následném
`record put` zachovat celý `source.acquisition` a doplnit identifikaci shodně
v `source.reference` i metadatech. Obrazové deriváty nadále patří do `crops/`.

## Evidence živého získání MZA (0.6.0)

U živého získání má `source.acquisition` navíc dva nepovinné objekty:

- `permission`: `basis: user_attestation`, `scope: single_image`, přesné
  uživatelské `statement`, `evidence_reference`, `recorded_at`, `sha256`
  původního soukromého JSONu a `min_interval_seconds`. Je to evidence tvrzení
  uživatele o souhlasu, nikoli programové ověření pravosti souhlasu MZA.
- `iiif`: přesná `info_url`, `version` (2/3), `request_count`, `image_requests`
  a `live_access_verified`. U mock testů je poslední hodnota vždy `false`.
  Skutečný síťový průchod ji nastaví až po získání úplného obrazu, ověření
  rozměrů a úspěšném importu. Neoznačuje genealogická tvrzení za ověřená.

Tyto objekty vznikají ve stejné atomické změně jako záznam. `project check`
kontroluje jejich strukturu; ZIP je přenese včetně soukromé citace souhlasu.
Plný konfigurační soubor není automaticky součástí přenosu ani globálním
oprávněním pro jiného uživatele. Obnovení projektu samo nepovolí živou síť.
Soukromá konfigurace patří mimo Git, s právy 0600.

Při chybě importu po úplném stažení zůstane kompletní PNG ve složce
`.mza-acquisition-*` v kořeni soukromého projektu; chyba vypíše přesnou cestu.
Lze jej znovu importovat bez nového stažení. Neúplný obraz se nepublikuje;
pomocná složka není zahrnutá do ZIPu, dokud neproběhne skutečný import.
Při opakovaném `download` již uložené přesné URL se použije místní kontrola,
bez sítě. Případnou novou archivní verzi je nutné vybrat a posoudit výslovně.

## Soukromá diagnostika MZA

Volitelné `archive mza download --diagnostics-dir <nová-složka>` ukládá
`response-0001.html/json/bin`, odpovídající `response-0001.metadata.json`
a souhrnný `attempt.json`. Metadata obsahují URL, HTTP stav, omezenou sadu
hlaviček, klasifikaci odpovědi, rozpoznané prvky, velikost a SHA-256 přijatého
a uloženého těla a příznak redakce. Cookies a autentizační hlavičky se neukládají;
známá citlivá pole se redigují. Názvy souborů se odvozují z pořadí, ne z URL.
Vše má práva 0600 a zůstává mimo Git. Výstup se nepřepisuje.

Diagnostika není genealogický pramen ani úspěšně stažený snímek. Doporučené
umístění je mimo `sources/`, `crops/` a `history/`; pak ji existující ZIP export
nezahrne. Při `active_challenge` se zachová odpověď a přesný důvod, ale nevzniká
import ani vizuální ověření. U některých transportních chyb před přijetím celé
odpovědi může být dostupný pouze souhrn chyby, nikoli tělo.

## Výřez

```sh
python3 scripts/family_tree.py image crop /soukroma/sources/scan.png /soukroma/crops/record.png --box 0.1,0.2,0.9,0.6
```

Výstup je PNG bez EXIF/GPS; originál zůstává beze změny. Souřadnice jsou po EXIF
orientaci. Nástroj nezvětšuje, nedoostřuje a nepřepisuje existující výřez.
Vrací JSON se souřadnicemi a součty; lze jej uložit do doplňkového pole `crop_metadata`.
Pro čtení vždy skutečně prohlédnout obrázek.

## Kontrolní obrázky

Funkce adaptované z původních nástrojů `overit.py`, `ramecek.py` a místního
režimu `mapa_knihy.py` jsou sloučené v jednom offline skriptu:

```sh
python3 scripts/family_tree.py image split /soukroma/sources/scan.png /soukroma/crops/left.png /soukroma/crops/right.png --box 0.1,0.2,0.9,0.6
python3 scripts/family_tree.py image mark /soukroma/crops/record.png /soukroma/crops/record-marked.png --box 0.05,0.1,0.95,0.8
python3 scripts/family_tree.py image sheet /soukroma/crops/book-map.png /soukroma/sources/scan-10.png /soukroma/sources/scan-20.png --box 0,0,1,0.15
```

`split` zachová překryv mezi částmi; `--contrast` vytvoří pracovní černobílou
kopii. `mark` zakreslí jeden či více rámečků (`--box` lze opakovat). `sheet`
slepí stejné oblasti již uložených snímků a nestahuje nic ze sítě. Vstupy musí
být běžné soubory, výstupy nové soukromé PNG mimo Git. Skript vrací SHA-256 a
původní soubory nemění.

## Kontrola a pokračování

```sh
python3 scripts/family_tree.py --workspace /soukroma project resume
python3 scripts/family_tree.py --workspace /soukroma record put /soukroma/zaznam.json --expected-revision 0 --next-step "Ověřit druhého stejnojmenného kandidáta."
python3 scripts/family_tree.py --workspace /soukroma project check
python3 scripts/family_tree.py --workspace /soukroma project audit
python3 scripts/family_tree.py --workspace /soukroma project log --result not_found --scope "Konkrétní kniha, snímky 12–16, hledané jméno" --expected-revision 1 --next-step "Projít rejstřík sňatků."
```

Revize jsou příklady, vždy načíst aktuální hodnotu.
`check` blokuje poškozený nebo nedoložený stav. `audit` je pouze čtecí kontrola
kvality: vypíše počty stavů a upozornění, která je nutné věcně posoudit.
