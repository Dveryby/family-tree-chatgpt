# MZA Brno: import jednoho snímku, živé IIIF zakázáno

## Oprávnění a aktuální hranice

Ověřeno 14. listopadu 2026 čtením veřejných stránek archivu:

- [Podmínky užití služeb](https://www.mza.cz/actapublica/page/view/podminky-uziti-sluzeb),
  zveřejněné 20. května 2024: použití a zveřejňování reprodukcí podléhá
  pravidlům archivu a vlastníků; technické zásahy vyžadují souhlas.
- [Nápověda, „Lze stáhnout snímek?“](https://www.mza.cz/actapublica/page/view/napoveda):
  uložení jednotlivého snímku či výřezu běžným prohlížečem, nejvýše 2000 bodů
  na delší straně. Kvalitnější kopii lze vyžádat na `badatelna@mza.cz` za úhradu.
- [Aktuality](https://www.mza.cz/actapublica/aktuality): upozornění z 14. ledna
  2022 na nepřípustné hromadné stahování nad 1,5 GB za den a blokace;
  zpráva ze 7. dubna 2026 popisuje také 24hodinové automatické blokace při
  velkém počtu digitalizátů za krátkou dobu.

Z těchto podkladů nevyvozujeme povolení automatického IIIF ani garantovaný
bezpečný počet požadavků. Denní limit není souhlas se skládáním plného snímku.
`archive mza download` proto vždy skončí vysvětlením bez síťového požadavku.
Neexistuje příznak, proměnná prostředí ani konfigurační volba k jeho aktivaci.
Živý IIIF průchod ani skutečné plné rozlišení MZA nebyly v této implementaci
ověřeny. Před budoucí změnou je nutný doložený souhlas pro konkrétní metodu,
ověření podmínek a limitů a samostatně ověřená síťová implementace.

## Podporovaný postup

1. Ve viditelném archivním prohlížeči ověřit obec, původce, skutečné číslo
   knihy, druh záznamů, rozsah let a konkrétní snímek. Interní číslo v cestě
   `/matrika/detail/…` není samo o sobě archivním číslem knihy.
2. Altcha, CAPTCHA nebo přihlášení řeší ručně uživatel. Při blokaci skončit;
   nepoužívat interní zdroje, tokeny, alternativní klienty ani adresy dlaždic.
3. Jeden snímek uložit standardní funkcí prohlížeče, zachytit screenshot nebo
   získat oficiální kopii od archivu. Původní soubor uchovat mimo Git.
4. Importovat jej do existujícího soukromého projektu. Příklady volají
   skripty relativně ke složce skillu:

```sh
python3 scripts/family_tree.py --workspace /private/research project init
python3 scripts/family_tree.py --workspace /private/research archive mza import /private/downloads/scan.jpg --url 'https://www.mza.cz/actapublica/matrika/detail/999999?image=synthetic-001.jp2' --method browser_download
python3 scripts/family_tree.py --workspace /private/research archive mza inspect --url 'https://www.mza.cz/actapublica/matrika/detail/999999?image=synthetic-001.jp2' --file /private/downloads/scan.jpg
```

URL v příkladu je **syntetická, neslouží k otevření archivu**. Nahradit ji
skutečně ověřeným odkazem. `--reference` a `--image-number` uvést pouze podle
podkladu; program je neodhaduje z názvu souboru nebo URL.

`inspect` kontroluje místní evidenci podle přesné URL a volitelně kontrolního
součtu. Bez `--workspace` vypíše omezení a případně metadata dodaného souboru;
nenačítá vzdálenou stránku, `info.json` ani chráněné zdroje. Jiná URL může být
aliasem stejného snímku; bez totožných bajtů se taková shoda automaticky netvrdí.

Přijímáme jeden úplně dekódovatelný soubor JPEG, PNG, TIFF nebo JP2 podle
podpory místního Pillow. Vícestránkové TIFFy se odmítají. Limit je 64 MiB,
40 milionů pixelů a 30 000 px na jednu osu. Ani oficiální kvalitnější kopie
se nezmenšuje automaticky; při překročení limitu import skončí vysvětlením.
Kopie se atomicky zveřejní pod názvem odvozeným od SHA-256 a skutečného formátu,
s oprávněním 0600. Nevzniká přepis jiného souboru. Zámek chrání revizi;
`--expected-revision` umožňuje výslovnou kontrolu souběžné změny.

Import nemění bajty, EXIF ani geometrické rozměry. Browserové kopie,
screenshoty a IIIF sestavy se evidují jako odvozené. Archivní kopii lze
označit `--digital-copy original` pouze s `--method archival_copy` a
`--provenance-note` uvádějící skutečný podklad, například potvrzení archivu.
Tento údaj je doložené prohlášení uživatele, nikoli nezávislý posudek nástroje.
Jinak zůstává digitální původ `unknown` nebo výslovně `derived`.
Datum `--acquired-at` má ISO formát s časovým pásmem; bez něj je evidován čas
importu jako čas převzetí této kopie do projektu, nikoli domnělé datum stažení.

Po importu pokračovat pomocí `image crop`, `split`, `mark`, `sheet` a skutečné
vizuální kontroly. Samotný import zanechává `unread`, `visual_review: false`,
`identity.status: unresolved`. Citaci, přepis a totožnost posuzovat samostatně.
Snímky i metadata zahrnuje stávající ZIP export a obnova.

## Offline adaptér IIIF

`scripts/mza.py` obsahuje oddělený `OfflineIIIF`, který přijímá výhradně
injektovaný mock transport bez síťového I/O a rezervovanou HTTPS doménu
`iiif.example.invalid`. Není propojen s příkazem `download`, nemá HTTP klienta
a neumí přeložit archivní detail na interní adresu snímku. Produkční domény
včetně MZA odmítá. TLS se nikde nevypíná; živý TLS transport není implementován.
Případný budoucí klient musí ověřovat certifikáty, DNS/IP i každé přesměrování.

Testuje běžná metadata [IIIF 2.1](https://iiif.io/api/image/2.1/) a
[IIIF 3](https://iiif.io/api/image/3.0/), skutečné rozměry, limity velikosti,
deklarované měřítko 1 a nekvadratické dlaždice včetně okrajů. Upřednostní jeden
celý obraz, pokud je podporován; jinak nejmenší počet podporovaných dlaždic.
Požaduje standardní JPEG a ukládá odvozený PNG bez další JPEG komprese.
Neoznačuje jej za původní JP2/TIFF. Nejde o podporu všech rozšíření IIIF,
nestandardních query endpointů IIPServeru ani autentizovaných služeb.

Mock požadavky jsou sekvenční, s 15s timeoutem a testovacím odstupem 2 s,
s nejvýše jedním opakováním timeoutu nebo HTTP 500/502/503/504. `Retry-After`
v sekundách či HTTP datu se respektuje; čekání nad 60 s operaci ukončí.
403, 401, 429, HTML ochrana, CAPTCHA/Altcha a jakékoli přesměrování okamžitě
zastaví relaci bez pokračování. 404 se neopakuje. Limity přenosu jsou
128 MiB a 2048 požadavků včetně metadat a opakování. Chybná, poškozená nebo
chybějící dlaždice znamená neúspěch bez publikování částečného obrázku.
Tyto parametry jsou testovací politika, nikoli archivem schválená rychlost.

## Dřívější živý pilot

11. listopadu 2026 bylo v prohlížeči Codex ověřeno hledání, detail knihy,
ruční Altcha a jeden snímek se screenshotem 1078 × 1034 px. Podrobnosti jsou
v `../../../docs/VALIDATION.md`. Pilot nedokládá oprávnění ani funkčnost IIIF.

Audit referenčního downloaderu, zdrojová revize a aktuální testy jsou rovněž
v `../../../docs/VALIDATION.md`. V ChatGPT bez lokálního Pythonu/Pillow či
souborového přístupu nezaručovat spuštění CLI; nabídnout import v lokálním Codexu.
