# MZA Brno: import a jednotlivé snímky s evidovaným souhlasem IIIF

## Oprávnění

[Podmínky užití](https://www.mza.cz/actapublica/page/view/podminky-uziti-sluzeb),
[nápověda](https://www.mza.cz/actapublica/page/view/napoveda) a
[aktuality](https://www.mza.cz/actapublica/aktuality) byly znovu přečteny
14. listopadu 2026. Nápověda veřejně dokládá uložení běžným prohlížečem do
2000 bodů na delší straně; kvalitnější kopie se objednává u archivu.
Tyto veřejné podklady samy nedokládají obecné povolení automatického IIIF.
Aktuality upozorňují na hromadné stahování a automatické blokace.

Od 0.6.0 lze živý režim použít na základě výslovného uživatelského potvrzení,
že uživatel má souhlas MZA pro IIIF. Program ho eviduje jako `user_attestation`,
neověřuje nezávisle pravost souhlasu ani nepovažuje potvrzení za veřejnou licenci.
Skutečný rozsah a případné další podmínky souhlasu musí být dodrženy. Samotný
příznak CLI není dokladem oprávnění. Bez soukromého záznamu zůstává síť vypnutá.

Potvrzení uložit mimo Git, standardně do
`~/.config/family-tree-chatgpt/mza-permission.json` (nebo pod `XDG_CONFIG_HOME`),
s právy 0600. Záznam je prostý JSON:

```json
{
  "schema_version": 1,
  "archive": "mza",
  "basis": "user_attestation",
  "scope": "single_image",
  "statement": "Zde uvést skutečné výslovné potvrzení uživatele o souhlasu MZA pro IIIF.",
  "evidence_reference": "Zde uvést dohledatelný podklad potvrzení, například konkrétní konverzaci nebo dokument.",
  "recorded_at": "2026-11-14T10:00:00+01:00",
  "min_interval_seconds": 2
}
```

Příklad je šablona, není udělením souhlasu. Volitelné `expires_at` obsahuje
ISO čas s pásmem; prošlý souhlas se odmítá. Odstup je nejméně 2 s, lze jej
zvýšit do 60 s podle skutečných podmínek. Výchozí odstup je konzervativní
místní nastavení, nikoli archivem schválený limit. Záznam se nesmí použít,
pokud konkrétní souhlas vyžaduje jiné, nepodporované podmínky.

## Jednotné CLI

Příklady volají skripty ze složky skillu; workspace i vstupy patří mimo Git.
URL níže je syntetická a musí se nahradit přesným ověřeným odkazem.

```sh
python3 scripts/family_tree.py --workspace /private/research project init
python3 scripts/family_tree.py --workspace /private/research archive mza import /private/downloads/scan.jpg --url 'https://www.mza.cz/actapublica/matrika/detail/999999?image=synthetic-001.jp2' --method browser_download
python3 scripts/family_tree.py --workspace /private/research archive mza inspect --url 'https://www.mza.cz/actapublica/matrika/detail/999999?image=synthetic-001.jp2'
python3 scripts/family_tree.py --workspace /private/research archive mza download --url 'https://www.mza.cz/actapublica/matrika/detail/999999?image=synthetic-001.jp2'
```

`download --permission-file /private/mza-permission.json` určí jinou evidenci
souhlasu. Lze doplnit známé `--reference`, `--image-number`, `--expected-revision`.
Interní ID detailu není číslo knihy a pořadí snímku se neodhaduje z JP2 názvu.

`inspect` je bez sítě: vypíše místní kopie, skutečné rozměry a stav soukromé
evidence oprávnění. `--file` porovná i SHA-256. Stav `download_allowed: true`
neznamená otevřenou relaci ani úspěšný živý průchod. Již uloženou přesnou URL
`download` znovu nestahuje. Import sám nevytváří vizuální ověření ani tvrzení.

## Živý průchod a šetrnost

1. Ověřit soukromý souhlas, workspace, revizi a URL jednoho konkrétního snímku.
2. Načíst pouze veřejný detail. Při CAPTCHA/Altcha, 401/403/429 nebo jakémkoli
   přesměrování zastavit celou operaci, bez jiného klienta nebo endpointu.
3. Přijmout pouze úplný obrazový zdroj zveřejněný na stránce, který přesně
   odpovídá vybranému JP2. Nenahrazovat názvy souborů ani neodhadovat složku.
   Pro zveřejněný zdroj IIPImage lze na stejném endpointu a přesně stejné
   cestě použít dokumentovaný přepínač IIIF místo Deepzoom; viz
   [IIPImage](https://iipimage.sourceforge.io/documentation/server/).
4. Načíst `info.json`, ověřit API 2/3, identitu, rozměry a limity. Upřednostnit
   jeden celý JPEG; pouze při nutnosti použít deklarované dlaždice v měřítku 1.
   Chyba, omezené rozlišení či neúplný obraz znamenají zastavení, ne další cestu.
5. Ověřit každou dlaždici i výsledný obraz. Uložit odvozený PNG bez další JPEG
   komprese a importovat do `sources/` se souhlasem a IIIF metadaty. PNG není
   původní JP2/TIFF. Zachovat `unread`, `visual_review: false` a neověřenou totožnost.

Povolené HTTPS domény jsou pouze `www.mza.cz` a `iipserver.mza.cz`, s omezenými
cestami a operacemi. TLS certifikáty i hostname se ověřují. DNS musí vrátit
výhradně veřejné IP; TCP spojení se připne k ověřenému výsledku při zachování
původního SNI/hostname. Přesměrování se nenásledují. Nepoužívají se proxy,
cookies, přihlašování ani automatické řešení ochran. Vždy jen jeden snímek,
sekvenčně, bez dávek a paralelních požadavků. Společný dočasný zámek pro
uživatele odmítne souběžný příkaz; po pádu ověřit proces před odstraněním
zámku. Souhlas se znovu kontroluje před každým požadavkem a jeho změna
nebo odvolání zastaví další síťový přístup.

Timeout je 15 s, nejvýše jedno opakování timeoutu nebo HTTP 500/502/503/504.
`Retry-After` v sekundách či HTTP datu se respektuje; nad 60 s operace skončí.
Limity: 2048 požadavků včetně detailu, metadat a opakování, 128 MiB přenosu,
64 MiB na obrazový soubor, 40 milionů pixelů a 30 000 px na osu. Obsah HTTP
se čte omezeně; velikost se kontroluje i bez Content-Length. Nepodporované
komprimované HTTP odpovědi se odmítají. Po blokaci nejsou další požadavky.

## Import, metadata a skutečně ověřený stav

Import přijímá jeden JPEG, PNG, TIFF nebo JP2 podporovaný místním Pillow,
bez změny bajtů nebo geometrie; vícestránkové TIFFy se odmítají. Screenshoty,
browserové kopie a IIIF jsou odvozené. `--digital-copy original` je možné jen
s `--method archival_copy` a skutečným podkladem v `--provenance-note`.
Neznámá identifikace zůstává prázdná. U importu `--acquired-at` určuje známý
čas získání s pásmem, jinak se eviduje čas převzetí při importu.

Soubor se atomicky zveřejní pod SHA-256, bez přepisování a s právy 0600.
Úplná kopie při následném selhání uložení stavu zůstane pro ruční import v
pomocné soukromé složce; příkaz vypíše její cestu. Export, obnova a stávající
`crop/split/mark/sheet` fungují nad importem. Podrobnosti: [data](data.md).

Uživatelské potvrzení souhlasu bylo poskytnuto 14. listopadu 2026. Skutečný
pokus téhož dne skončil na prvním veřejném detailu s HTTP 200 při detekci
obsažené ochrany; žádné info.json, obrazové zdroje ani dlaždice nebyly dále
oslovovány. Úspěšné živé stažení ani skutečné plné rozlišení se zatím netvrdí.
Offline testy ověřují stejný průchod přes mock HTTPS. Dřívější skutečný pilot
z 11. listopadu zachoval jen browserový screenshot 1078 × 1034 px.
Další důkazy a omezení jsou v `../../../docs/VALIDATION.md`.

V ChatGPT bez lokálního Pythonu/Pillow, souborů nebo síťových oprávnění
neslibovat spuštění; použít dostupný import a sdělit konkrétní omezení prostředí.
