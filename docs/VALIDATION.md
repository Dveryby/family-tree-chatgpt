# Ověření verze 0.4.5

Datum: 10.–13. listopadu 2026. První průchod: Linux, Python 3.12.14,
Pillow 13.0.0. Rozšířená sada 56 testů byla znovu spuštěna na Pythonu 3.13.5
s Pillow 11.1.0; osm testů ověřuje Gramps adaptér a čtyři balení pluginu.

## Gramps Tasks ve verzi 0.4.5

Dne 13. listopadu 2026 přibyly příkazy `gramps tasks probe/plan/push`.
Rozšířená sada **56 testů prošla**. Dva nové syntetické testy ověřují vytvoření
tagu `ToDo`, standardních soukromých objektů `Source` a `Note`, stabilní
identifikátory, opakovaný push bez duplicit, zachování uživatelsky změněného
stavu, priority, titulu a popisu a odmítnutí duplicitních tagů i kolize objektu.
HTTP test navíc kontroluje přesné cesty `/api/tags/`, dotaz na seznam tagů a
serializaci vytvoření tagu. Do skutečného Gramps stromu úkol zapsán nebyl.

## Automatické testy

Příkaz z kořene repozitáře:

```sh
python3 -m unittest discover -s tests -v
```

Výsledek: **56 testů prošlo**.

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
- Export úplného stavu přes CLI, manifest s velikostmi a SHA-256 a obnova do
  nové složky se shodnou revizí, historií, snímkem a výřezem.
- Pokračování další revizí po obnově; odmítnutí změněného obsahu, nebezpečné
  cesty, symlinku, cíle v git repozitáři a přepsání existujícího projektu.
- Úklid neúplné obnovy a zámku po odmítnuté operaci.
- Import syntetického GEDCOM 5.5.1 s osobami, rodinou, událostmi, pramenem,
  pokračováním textu a uživatelským rozšířením.
- Rozlišení GEDCOM tvrzení od ověřených důkazů a vytvoření plánu pro chybějící
  narození/křty a události bez použitelného pramene.
- Odmítnutí porušené hierarchie, duplicitních identifikátorů, ANSEL vstupu,
  vstupních či výstupních symlinků, přepsání výstupu a uložení soukromého
  importu do git repozitáře.
- Zachování chybějících rodinných a zdrojových odkazů jako varování, nikoli faktů.
- Volitelná GEDCOM fronta předků s Kekulého čísly, pracovní kotvou, limitem
  generací i počtu pozic, zastavením při více nerozlišených `FAMC` rodinách a
  detekcí cyklu.
- Rozdělení místního snímku na překrývající se části, označení kontrolované
  oblasti a montáž již uložených snímků; zachování originálu, odstranění EXIF,
  oprávnění `0600`, zákaz přepsání, symlinků a výstupu do Git repozitáře.
- Čtecí `audit` výzkumného stavu: počty stavů, chybějící překlad či
  interpretace, otevřené nejistoty, závěr o totožnosti před kontrolou čtení a
  možné duplicitní citace; audit stav nemění.
- Formát 2 s osobami, vztahy, tvrzeními, prameny a konflikty: atomické vložení,
  odkazy mezi kolekcemi, stavy tvrzení, citace, zdůvodněné řešení konfliktu a
  kontrola SHA-256 souboru pramene.
- Odmítnutí chybějících osob/pramenů/tvrzení, neznámých polí, neplatných ID,
  prázdné změny a změny se starou očekávanou revizí bez částečného zápisu.
- Výslovná migrace formátu 1 na formát 2 se zachováním záznamů, událostí,
  předchozí revize v `history/` a bez automatického vytváření genealogických faktů.
- Jednotné CLI `family_tree.py`: společný průchod příkazy `project`, `record`,
  `model`, `gedcom` a `image`, včetně čtecího výběru jedné modelové entity.
- Gramps Web: syntetické mapování pouze podporovaných tvrzení, vyloučení
  neověřených tvrzení a otevřených konfliktů, soukromé osoby, událost a
  rodičovská rodina, stabilní identifikátory a zdrojové poznámky.
- Příkazy `gramps probe`, `plan`, `push` a `status` nad in-memory náhradou API:
  oprávnění `0600` plánu, opakovaný stav `synchronized`, kontrola hashů,
  odmítnutí kolize, změněného plánu a nešifrovaného HTTP.
- Příkazy `gramps tasks probe`, `plan` a `push`: tag `ToDo`, soukromé úkoly,
  stabilní handles, idempotentní opakování a zachování uživatelských změn.
- Plugin: přenosný manifest Agent Plugins 1.0, kompatibilní manifest pro Codex,
  shoda verze `0.4.5`, metadata rozhraní a repozitářový marketplace ukazující
  na kořen balíčku.

Strukturální validace balíčku proběhla nástrojem `quick_validate.py` bez chyb.

## Instalace pluginu v ChatGPT desktop 13. listopadu 2026

Níže uvedené praktické ověření instalace proběhlo s verzí 0.4.0. Balení 0.4.5
je ověřeno automatickými testy; nová instalace do desktopové cache zde
provedena nebyla.

Repozitář byl ověřen jako skills-only plugin dvěma nezávislými validátory:

- `quick_validate.py` přijal `skills/family-tree-chatgpt`,
- `validate_plugin.py` přijal kompatibilní `.codex-plugin/plugin.json`,
- všechny tři JSON soubory byly znovu načteny standardním parserem Pythonu.

Desktopový plugin runtime z instalace ChatGPT následně provedl tento průchod:

- `plugin marketplace add` přidal kořen repozitáře jako marketplace
  `family-tree-chatgpt`,
- `plugin list --available` našel `family-tree-chatgpt` ve verzi `0.4.0`,
- `plugin add` vytvořil instalační kopii v desktopové plugin cache,
- závěrečný `plugin list` hlásil `installed: true` a `enabled: true`,
- instalovaný `plugin.json` a `SKILL.md` byly binárně shodné se zdrojem a
  instalovaná kopie obsahovala hlavní `scripts/family_tree.py`.

Nová konverzace je hranicí pro načtení nově instalovaného skillu; aktivní
konverzace se během instalace nerestartovala.

## Syntetická integrace Gramps Web 12. listopadu 2026

Vedle in-memory API testů proběhl úplný průchod proti oficiálnímu obrazu
`ghcr.io/gramps-project/grampsweb:latest` s digestem
`sha256:80a1d75ca0f67f9203aecca60f7639312a2769fe0af45b34608b0add64f7c07f`.
Dočasná instance bez svazků hlásila Gramps Web API 3.25.2, Gramps 6.0.8 a
datové schéma 21.0.0. Syntetický účet měl roli Editor; spojení bylo pouze na
lokálním portu a HTTP bylo povoleno výslovným testovacím přepínačem.

První skutečný požadavek zachytil dvě odlišnosti od starší statické OpenAPI
specifikace 3.7.2: kolekce používají koncovou lomítkovou cestu, zatímco detail
objektu nikoli, a `SrcAttribute` má užší pole než obecný atribut. Adaptér byl
zúžen na společnou podmnožinu a rozlišuje oba tvary endpointů. Další čistý
průchod v novém prázdném kontejneru doložil:

- `probe`: kompatibilní API a správná identita prázdného stromu,
- `plan`: 20 operací `create`, žádná kolize ani varování,
- `push`: 20 objektů vytvořeno a všech 20 zpětně načteno a ověřeno,
- `status`: `synchronized`, 20 `unchanged`, 0 `create`, 0 `conflict`.

Scénář obsahoval dva syntetické lidi, jedno datum narození, jeden doložený
rodičovský vztah, archiv, pramen, sedm citací a sedm výzkumných poznámek.
Kontejner běžel s `--rm`, bez hostitelských svazků, a po ověření byl odstraněn.
Žádné skutečné rodinné údaje ani soukromý produkční server nebyly použity.

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

## Lokální export a obnova 12. listopadu 2026

Syntetický stav s jedním vizuálně zkontrolovaným záznamem a jednou událostí
prošel přes `put → log → export`. Vytvořený ZIP obsahoval `research.json`,
historii, zdrojový obrázek, výřez a manifest s revizí, velikostmi a SHA-256.
Příkaz `restore` jej obnovil do nové složky, kde `check` i `resume` potvrdily
shodný stav. Následný `log` vytvořil další revizi, takže nešlo jen o čtení
archivu, ale o skutečné navázání na obnovený stav.

Samostatné testy změnily bajt zdrojového obrázku bez úpravy manifestu a ověřily
odmítnutí balíčku i odstranění dočasné obnovy. Ověřeno bylo také odmítnutí
`../` cesty, symlinku, výstupu v git repozitáři a existující cílové složky.

Stejný lokální průchod byl proveden také se soukromou pracovní kopií pilotu
MZA: citace knihy 2726, screenshot snímku 2 a jeho výřez byly uloženy jako
`draft` bez vymyšleného přepisu. `check` potvrdil revizi 1 a jeden záznam.
Export obsahoval čtyři datové soubory a manifest; SHA-256 výsledného ZIP je
`25c7d3ef72da568372c0be622f01a70b87531d83f55ad1e993d0d98d3fa2dddd`.
Obnova do nové složky zachovala SHA-256 screenshotu i výřezu a následný zápis
poznámky vytvořil revizi 2. Soukromé pracovní soubory a ZIP zůstaly mimo
repozitář.

## Přenos přes trvalé úložiště a novou konverzaci 12. listopadu 2026

Soukromý stav pilotu MZA v revizi 2 byl exportován mimo repozitář do trvalého
soukromého úložiště. Nová uživatelská konverzace dostala projekt a tento ZIP,
nikoli historii původní konverzace. Příkaz `restore` obnovil stav do nové složky;
`check` a `resume` potvrdily revizi 2, jeden záznam, uložený další krok a shodné
SHA-256 zdrojového screenshotu a výřezu.

Nová konverzace následně skutečně pokračovala zápisem celé další revize s
`--expected-revision 2`. Vznikla revize 3, `check` ji označil za platnou a
`resume` ji znovu načetl. Nový balíček byl uložen v soukromém úložišti jako
`mza-badani-r3-2026-11-12.zip`; jeho SHA-256 je
`81452c270c08c0aca1a605214933079a92851899537bca425b05de928f99745a`.
Soukromý přepis ani obrazová data nejsou součástí repozitáře.

Tím je prakticky ověřen přenos úplného stavu přes trvalé soukromé úložiště,
obnova v nové konverzaci a pokračování novou revizí. Paleografická správnost
pracovního přepisu tím potvrzena není.

## Dokončení prvního skutečného zápisu 12. listopadu 2026

Revize 3 byla z trvalého soukromého úložiště obnovena do nové pracovní složky.
První řádek snímku 2 matriky MZA č. 2726 byl znovu porovnán se živým archivním
prohlížečem při větším zvětšení. Datum, pokřtěný, rodiče, kmotři, obec a zápis
křtícího byly vizuálně zkontrolovány. Historický pravopis zůstal v přepisu,
normalizace byla oddělena do českého překladu a nerozvedená zkratka zůstala
výslovně nejistá. Totožnost s jinou osobou nebyla bez dalšího pramene tvrzena.

Úplný záznam obsahující přepis, překlad, interpretaci a nejistoty byl uložen s
`--expected-revision 3` jako revize 4 a stavem `reviewed`. `check` vrátil
`valid: true`, revizi 4 a jeden záznam; `resume` načetl shodný další krok.
Soukromý export `mza-badani-r4-2026-11-12.zip` obsahuje sedm datových souborů
a má SHA-256
`f5ace1408c1392fca6cfce7b4545ce388f9848bbfa1d3439544c08a17c53d5fa`.
Přepis a obrazová data zůstávají mimo repozitář.

První projektový milník je tím doložený od živého pramene přes strukturovaný
výsledek až po navázání v nové konverzaci. Stav `reviewed` potvrzuje provedenou
vizuální kontrolu, nikoli ztotožnění osoby nebo bezchybnou modernizaci jmen.

## Co ověřeno není

- Nezávislá druhá paleografická kontrola a modernizace historických příjmení.
- Funkčnost na Windows/macOS či Pythonu 3.11; vyzkoušeno bylo uvedené linuxové prostředí.
- Import skutečného uživatelského GEDCOMu; automatické testy používají pouze
  syntetická data. Gramps adaptér je ověřen syntetickými API odpověďmi a
  dočasnou skutečnou instancí, ale ne produkční soukromou instancí ani
  skutečnými rodinnými údaji. Dále nejsou ověřeny automatické hledání, původní
  databázové schéma ani rodinný web.
- Obrazové deriváty `image_review.py` jsou automaticky ověřené na syntetických
  obrázcích, ne na reprezentativním souboru různých skutečných archivních
  formátů a kvalit.

## Audit původního projektu 12. listopadu 2026

Z GitHubu byla načtena přesná revize
`0fb0c0379abf51a9af92d363992799fcd38eb23a`; při kontrole byla zároveň
aktuálním `origin/HEAD` původního projektu. U všech 31 nástrojů v
`skills/rodokmen/tools` byl porovnán deklarovaný účel, importy, externí
závislosti, síťový přístup a vazba na datový model. Úplná rozhodnutí a SHA-256
jsou v `docs/PORTING.md`.

Do této verze byly přepsány pouze offline části, které lze bezpečně testovat na
syntetických datech: kontrolní obrazové deriváty, fronta předků a audit kvality.
Metodická pravidla byla zkráceně adaptována do samostatné reference. Síťové
downloadery nebyly spuštěny ani převzaty; jejich historická přítomnost v
upstreamu není důkazem dnešní dostupnosti či oprávnění portálu.

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

## Import MZA a offline IIIF, 14. listopadu 2026 (0.5.0)

Audit před implementací zahrnul README, AGENTS, aktuální skill, reference
MZA/data, jednotné CLI, ukládání stavu, ZIP přenos a existující testy.
Výchozí čistá větev `main` byla na revizi `7781926`; původních 56 testů prošlo.
Implementace vznikla na `feature/mza-image-acquisition`.

### Podmínky archivu

Přečteny oficiální [podmínky](https://www.mza.cz/actapublica/page/view/podminky-uziti-sluzeb),
[nápověda](https://www.mza.cz/actapublica/page/view/napoveda) a
[aktuality](https://www.mza.cz/actapublica/aktuality). Nápověda dokládá
browserové uložení jednotlivého snímku/výřezu do 2000 bodů na delší straně
a kvalitnější kopii na vyžádání u MZA. Povolení automatického skládání IIIF
v těchto podkladech nalezeno nebylo. Zpráva ze 7. dubna 2026 navíc upozorňuje
na 24hodinové blokace při vysokém počtu požadavků na digitalizáty.

Produkční obrazové zdroje, info.json ani dlaždice nebyly oslovovány.
Zákaz síťového přístupu MZA zůstává zachovaný; `download` vždy odmítne operaci
ještě před sítí. Testovací adaptér nemá produkční HTTP/TLS transport,
neřeší mapování detailu matriky na obrazovou službu a odmítá skutečné domény.
Neexistuje aktivace příznakem CLI. Pro případnou budoucí aktivaci zbývá doložit
oprávnění, pravidla rychlosti a implementovat i ověřit bezpečný živý transport
s TLS, ochranou proti SSRF a kontrolou přesměrování. Dosavadní pilot screenshotu
z 11. listopadu tuto podmínku nenahrazuje.

### Referenční projekt a původ implementace

Prostudován [actapublica-image-downloader](https://github.com/lffelmann/actapublica-image-downloader)
na revizi `8b9420f6368533588e8e292039980acf6b3c7610`, soubory `main.py`,
`README.md`, `requirements.txt` a `LICENSE` (Unlicense). Používá requests,
Pillow a urllib3. Audit našel vypnuté TLS, pevnou konstrukci obrazové adresy,
chybějící úplnou validaci metadat a okrajových dlaždic a pokračování po chybě
dlaždice až k uložení neúplného obrazu. Kód ani dokumentace nebyly převzaty;
nový modul je samostatná implementace v rámci stávajícího projektu, bez nových
závislostí. Původní MIT oznámení projektu zůstávají zachovaná.

Plánování a syntaktické rozdíly obrazových požadavků ověřeny proti oficiálním
specifikacím [IIIF 2.1](https://iiif.io/api/image/2.1/) a
[IIIF 3](https://iiif.io/api/image/3.0/). Adaptér zpracovává jejich běžnou
podmnožinu; kompatibilita s reálnými endpointy MZA se tím netvrdí.

### Důkazy testů

Prostředí: Python 3.13.5, Pillow 11.1.0, dostupný dekodér JPEG2000.
Spuštěno `python3 -m unittest discover -s tests -v`:
**88 testů, 6,830 s, OK**; z toho **32 nových testů** v `tests/test_mza.py`.
Testy používají pouze generované obrázky, dočasné soukromé složky a mock
HTTP server v paměti; nespoléhají na produkční síť ani živý server MZA.

Ověřeno:

- bezeztrátový import bajtů PNG, JPEG, TIFF i JP2 a rozpoznání skutečného
  formátu přes zavádějící příponu, odmítnutí vícestránkového TIFFu;
- původ, čas, rozměry, velikost, SHA-256 a oprávnění kopie 0600;
- zachování `unread`, neověřené totožnosti a prázdného modelu tvrzení;
- opakovaný import bez změny revize a bez ztráty rozpracovaného přepisu;
- stejné bajty s různými URL a různé bajty se stejnou URL bez záměny původu;
- kontrola integrity, metadat, symlinků, Git umístění, limitů a staré revize;
- odmítnutí kolize souboru i ID, souběžné zveřejnění bez přepsání a úklid
  po selhání uložení stavu;
- stávající `crop`, `split`, `mark`, `sheet`, ZIP export, obnova i pokračování;
- import a obnova ve formátu 1 bez automatické migrace, následná výslovná migrace;
- metadata IIIF 2/3, chybná/neúplná metadata, limity a implicitní maxHeight,
  nejméně požadavků, nekvadratické a okrajové dlaždice, přesná shoda všech
  výsledných pixelů s dekódovanými JPEG dlaždicemi;
- chybějící, poškozené a nesprávně velké dlaždice bez publikování obrazu;
- HTTP 401/403/404/429/500/503, timeout, jediné opakování přechodných chyb,
  Retry-After v sekundách i HTTP datu a ukončení při příliš dlouhém čekání;
- blokace/HTML/Altcha, odmítnutí všech přesměrování a nepovolených domén,
  path traversal, zastavení relace a omezení přenosu i počtu požadavků;
- zakázaný downloader a odmítnutí domnělého aktivačního příznaku;
- shoda verze 0.5.0 v obou manifestech a VERSION; stávající marketplace
  nadále odkazuje na stejný kořen a vlastní pole verze nemá.

### Skutečně ověřená rozlišení a omezení

| Podklad | Výsledné rozlišení | Co prokazuje |
| --- | --- | --- |
| Syntetický import PNG, včetně ZIP obnovy a obrazových příkazů | 2101 × 1703 px | Zachování místní kvalitní kopie bez zmenšení |
| Syntetická IIIF 2/3 sestava z 12 JPEG dlaždic 173 × 127 px | 517 × 389 px | Správné složení včetně poslední dlaždice 171 × 8 px |
| Syntetický celý IIIF 2/3 obraz | 517 × 389 px | Volba jediného obrazového požadavku |
| Syntetické importy JPEG, PNG, TIFF, JP2 | 31 × 23 px | Detekce formátu a nezměněné bajty |
| Dřívější skutečný screenshot MZA (11. listopadu) | 1078 × 1034 px | Pouze tehdejší browserový pilot, ne plné rozlišení |

Rozměry z README cizího downloaderu nejsou výsledkem našeho testu. Skutečné
plné rozlišení MZA nebylo získáno ani ověřeno. Hotová je bezpečná importní
část a testovaný offline adaptér; živé stahování zůstává nepovolené a neověřené.
Žádný test neověřuje paleografii, totožnost osoby ani pravost archivní kopie.
Nové soubory obsahují obecný kód a syntetické údaje; rodinné snímky, přepisy,
GEDCOM ani přístupové údaje se do změny nepřidávají.
