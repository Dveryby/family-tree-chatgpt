# Ověření první lokální verze

Datum: 10. listopadu 2026. Prostředí: Linux, Python 3.12.14, Pillow 13.0.0.

## Automatické testy

Příkaz z kořene repozitáře:

```sh
python -m unittest discover -s tests -v
```

Výsledek: **16 testů prošlo**.

- Přesné pixely a velikost výřezu; zachování originálu; EXIF orientace.
- Odmítnutí chybných či prázdných souřadnic a přepsání výstupu/originálu.
- Ochrana před zápisem badatelských dat do skutečného git repozitáře.
- Uložení, kontrola a obnovení stavu v samostatných procesech CLI.
- Zachování ostatních záznamů, historie a negativních hledání.
- Odmítnutí staré revize a souběžného zapisovatele.
- Zachování původního stavu při simulované chybě atomické náhrady souboru.
- Detekce změněného snímku pomocí SHA-256 a odmítnutí dalšího zápisu.
- Odmítnutí cest mimo soukromou složku včetně symlinků.
- Vyžadování citace a vizuální kontroly pro stav `reviewed`.
- Vyžadování zdůvodnění a citací pro závěr o totožnosti.
- Srozumitelné chyby pro neplatné typy vybraných polí.

Strukturální validace balíčku proběhla nástrojem `quick_validate.py` bez chyb.

## Průchod pracovním postupem

Samostatný kontext dostal pouze pracovní postup, syntetický obrázek s latinským
textem a otázku, zda lze Jana ztotožnit s přibližně stejně starým Janem neznámého původu.
Obrázek byl výslovně označen jako smyšlený příklad; žádné rodinné údaje nebyly použity.

Výsledek po skutečném prohlédnutí obrázku: přepis, český překlad, oddělená interpretace,
`reading_status: draft`, `visual_review: true`, `identity.status: unresolved`.
Chybějící archivní citace nebyla doplněna smyšleným odkazem.

Proběhlo `init → resume → put → log note → check → resume`. Kontrola vrátila
`valid: true`, revizi 2 a jeden záznam. Původní obrázek zůstal shodný.
Průchod odhalil příliš široké odmítání pracovních složek podle pouhé existence
adresáře se jménem git metadat. Rozpoznání skutečného repozitáře bylo opraveno,
ověřeno regresními testy a průchod byl dokončen přímo do určené složky.

## Co ověřeno není

- Čtení historického rukopisu a jeho paleografická správnost.
- Uložení celé soukromé složky do trvalého úložiště a obnovení v nové uživatelské konverzaci.
- Funkčnost na Windows/macOS či Pythonu 3.11; vyzkoušeno bylo uvedené linuxové prostředí.
- GEDCOM, Gramps, automatické hledání, původní databázové schéma a web.

První projektový milník se skutečným pramenem proto zůstává otevřený.

## Živé ověření Opavského archivu 11. listopadu 2026

V prohlížeči Codex na Linuxu byla otevřena výchozí adresa
`https://digi.archives.cz/da/`. Portál nejprve zobrazil kontrolu Radware a poté
hCaptcha s incidentem `61e32736-dj82-4b32-8115-05546762ee62`. CAPTCHA byla
vyřešena ručně uživatelem; ochrana nebyla obcházena.

Po odblokování proběhlo přes viditelné rozhraní hledání matrik pro Hradec nad
Moravicí v rozmezí 1700–1800. Nalezeno bylo devět knih. Pro technický pilot byla
otevřena matrika narozených s touto ověřenou citací:

> Zemský archiv v Opavě, NAD 165 Sbírka matrik Severomoravského kraje I,
> Farní úřad Hradec, sign. Hr I 1, inv. č. 615, N 1643–1807, snímek 1.

Detail knihy uváděl 387 snímků. Snímek 1 byl skutečně otevřen a vizuálně
zkontrolován; obsahuje stránku s nadpisem „ANNO 1643“ a tabulkovými zápisy.
Ověřené trvalé odkazy:

- záznam: `https://digi.archives.cz/da/permalink/be8453fc-f13c-102f-8255-0050568c0263`
- snímek: `https://digi.archives.cz/da/permalink/be8453fc-f13c-102f-8255-0050568c0263/3986823a006a4318b8e8f7bace1b7d5b`

Vestavěné tlačítko „Uložit obrázek“ nevyvolalo standardní stažení a konzole
portálu hlásila `sendInput is not defined`. Prohlížeč však už měl z oficiálního
serveru `images.archives.cz` načtené všechny dlaždice nejvyšší zobrazené úrovně
Zoomify pro tento jediný snímek. Ty byly uloženy beze změny v soukromé pracovní
složce mimo repozitář, opatřeny SHA-256 a složeny do bezztrátového PNG o rozměru
886 × 660 px. Projektový `crop.py` z něj vytvořil a vizuálně ověřil výřez celé
matriční strany 478 × 640 px. SHA-256 složeného snímku je
`eb510236d260258a9ae95ae110d25b2e7e657b0add290a91e57e7ca583b0cb71`, výřezu
`1890d03dc60a1ff4d673cbf74429ae72b9a5e13968afb0d84ed3c596a12813e4`.

Ověřeno je tedy ruční odblokování, hledání, identifikace knihy, otevření jednoho
snímku, trvalé odkazy, citace, lokální zachování načtených obrazových dat a
výřez. Neověřuje to paleografickou správnost čtení ani automatické procházení;
CAPTCHA zůstává úmyslně ručním krokem a dávkové stahování nebylo prováděno.

## Živé ověření MZA Brno 11. listopadu 2026

V témže prostředí byl otevřen oficiální portál
`https://www.mza.cz/actapublica/`. Vyhledávání podle obce „Klobouky u Brna“
vrátilo mimo jiné nejstarší knihu č. 2726. Při otevření detailu portál zobrazil
Altcha; ověření provedl ručně uživatel a ochrana nebyla obcházena.

Po odblokování byly ve viditelném rozhraní ověřeny tyto údaje:

> Moravský zemský archiv v Brně, Acta Publica, matrika č. 2726, původní č. 1025,
> svazek I, původce Klobouky u Brna, římskokatolická církev, N 1665–1683,
> O 1665–1684, Z 1665–1684, snímek 2 z 210.

Kniha zahrnuje Borkovany, Klobouky u Brna, Bohumilice, Krumvíř a Velké
Hostěrádky. Snímek 2 byl skutečně otevřen a vizuálně zkontrolován; obsahuje
tabulkové křestní zápisy z roku 1665 na stranách označených 4–5. Přesný ověřený
odkaz na tento snímek je:

`https://www.mza.cz/actapublica/matrika/detail/2736?image=216000010-000253-003370-000000-002726-000000-00-B01685-00020.jp2`

Kvůli ochraně portálu nebyly použity přímé obrazové adresy, tokeny, dlaždice,
stahování ani skládání snímku. Zachován byl pouze screenshot viditelného
prohlížeče o rozměru 1078 × 1034 px. Nejde o archivní originál ani plné
rozlišení. SHA-256 screenshotu je
`5c7bafa64ce4a3026856d3e488867b8ee9b6108fb50e4703be9273a240912f78`.
Projektový `crop.py` vytvořil z prvního řádku zápisu vizuálně ověřený výřez
918 × 124 px se SHA-256
`38c095aa50fe37ba1106fec39abc8a3ef72b0480e552f091b3cdbcd8e5298c85`.

Ověřeno je tedy hledání, detail knihy, ruční Altcha, jeden konkrétní snímek,
citace, přesný odkaz a výřez ze screenshotu. Neověřuje to paleografickou
správnost čtení, automatické procházení, přímé stažení obrazu ani trvalost
uživatelské relace. Altcha zůstává úmyslně ručním krokem.
