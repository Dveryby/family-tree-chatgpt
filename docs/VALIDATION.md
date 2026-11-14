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

## Živý režim MZA se soukromým potvrzením souhlasu, 14. listopadu 2026 (0.6.0)

Na následný požadavek uživatel výslovně potvrdil, že má souhlas MZA pro IIIF.
Implementace toto potvrzení eviduje jako `user_attestation`, nikoli jako
nezávisle ověřený archivní dokument nebo veřejnou licenci. Konkrétní potvrzení
je uložené pouze v soukromém uživatelském nastavení mimo Git, s právy 0600.
Veřejné podmínky/nápověda/aktuality byly znovu přečteny; jejich výklad se tím
nemění a nevydáváme je za obecné povolení IIIF.

`archive mza download` nyní používá oddělený `mza_live.py`: nejprve ověří
soukromou evidenci souhlasu a jeden přesný odkaz, potom načte veřejný detail,
vybere pouze úplný zveřejněný zdroj stejného JP2 a získá IIIF obraz. Přepínač
IIIF na stejném IIPImage endpointu odpovídá
[oficiální dokumentaci IIPImage](https://iipimage.sourceforge.io/documentation/server/).
Není převzat cizí kód ani pevná konstrukce adresáře či náhrada názvu souboru.

Síťový transport ověřuje certifikáty i hostname, kontroluje doménu, cestu,
parametry a veřejné DNS adresy a připíná TCP cíl při zachování původního SNI.
Neobsahuje cookies, přihlašování ani řešení ochran. Všechna přesměrování,
HTTP 401/403/429 a ochranný obsah relaci zastaví. Rozměry, dlaždice, přenos,
timeout, Retry-After a atomické ukládání se kontrolují stejně jako v offline
adaptéru. Souhlas i parametry IIIF jsou součástí atomicky ukládaného záznamu,
kontroly stavu a exportu/obnovy. Při chybě importu zůstává úplný PNG pro
ruční převzetí bez dalšího stahování. Již uložená přesná URL se znovu nestahuje.

### Skutečný síťový pokus

Po úspěšných testech byl proveden jediný pokus proti veřejnému detailu
z příkladu referenčního projektu (interní detail 7163). Transport dostal
HTTP 200 a původní textová shoda captcha/altcha operaci ukončila ještě před
vyhledáním obrazové adresy. HTML tehdy nebylo uložené; tento výsledek sám
neprokazoval aktivní ochranu a následně byl takto upřesněn. Žádné info.json, snímek ani dlaždice nebyly poté požadovány.
Nebyl použit alternativní klient, ruční odemykání, token ani jiná síťová cesta.
Soukromý výsledek pokusu a prázdný projekt zůstaly mimo Git.

Ověřeno je skutečné HTTPS spojení k detailu a bezpečné zastavení, nikoli
úspěšné živé stažení. Skutečné plné rozlišení MZA ani čitelnost archivního
snímku se tím neprokazují. Rozměry 517 × 389 px v nových síťových testech
pocházejí výhradně ze syntetického mock serveru. Předchozí obrázky a piloty
zůstávají historickými výsledky popsanými výše.

### Automatické ověření

Python 3.13.5 / Pillow 11.1.0: celá sada po doplnění síťových testů obsahuje
**105 testů, OK**, z toho 17 nových testů v `tests/test_mza_live.py`.
Testy nevytvářejí produkční HTTP požadavky. Ověřují:

- chybějící, neplatné, prošlé, nezabezpečené nebo symlinkové potvrzení a
  neplatnou revizi či číslo snímku ještě před jakýmkoli požadavkem;
- API 2/3, jeden celý obraz i dlaždice přes stejný živý tok s mock transportem;
- uložení souhlasu a IIIF metadat, jejich poškození, export a obnovu;
- duplicitní požadavek bez sítě a zachování úplné kopie při chybě importu;
- přesnou identitu zveřejněného zdroje, JS escapování, odmítnutí chybějícího,
  nejednoznačného nebo jiného JP2 bez odhadování adresáře;
- domény, neveřejné/mapované IP, traversal a DNS pinning s původním TLS hostname;
- zapnuté ověřování certifikátů a odmítnutí TLS chyby bez obcházení;
- kontrolu deklarované i průběžně čtené délky, truncation a okamžitou reakci
  na blokaci bez čtení jejího těla;
- zastavení ochranného obsahu také za prvních 64 KiB HTML a žádný další endpoint.

Verze 0.6.0 je sjednocená v obou manifestech a VERSION. Nové repozitářové
soubory obsahují jen obecný kód a syntetické testy; konkrétní souhlas,
konfigurační soubor ani soukromý výsledek skutečného pokusu nejsou součástí změn.

Dodatečně ověřen společný zámek proti paralelním příkazům, odvolání či změna
souhlasu mezi požadavky a započtení částečně přijatých bajtů při timeoutu
do celkového přenosového limitu. V tomto původním běhu se živý pokus
neopakoval; pozdější opakování na výslovný požadavek je popsáno níže.


## Oprava detekce a uložená diagnostika MZA, 14. listopadu 2026

Původní detektor zastavoval HTML s pouhým výskytem slov captcha/altcha,
tedy i běžný odkaz na skript. Nahrazen je strukturálním parserem HTML:
ignoruje skripty, styly, komentáře, odkazy, text a neaktivní šablony; rozpoznává
konkrétní widgety nebo ochranné formuláře. HTTP 401/403/429, přesměrování,
HTML místo IIIF a chyba parsování mají samostatné klasifikace. Bez důkazu
konkrétního prvku se už samotné slovo nevydává za aktivní výzvu.

Přidán volitelný `--diagnostics-dir` pro novou soukromou složku mimo Git.
Ukládá odpovědi před rozhodnutím o pokračování, konkrétní signály, HTTP stav,
vybrané hlavičky, velikost, SHA-256 přijatých a uložených bajtů a souhrn pokusu.
Cookies a autentizační hlavičky se neukládají; známá citlivá pole se redigují.
Případná redakce je výslovně označená. Diagnostika má práva 0600 a nesmí
přepsat existující složku. V tomto PR se nezveřejňují skutečné HTML odpovědi.

### Doložený výsledek opakovaného pokusu

Na výslovný požadavek proběhl jeden nový pokus se stejným veřejným detailem
(interní ID 7163) dne 14. listopadu v **09:27:52 SEČ**. Uložená odpověď:

- HTTP **200**, `text/html; charset=UTF-8`, **22 826 bajtů**;
- SHA-256 přijatého i uloženého HTML:
  `c21336f1cafe56e8f77b26bc227b42ecd0bff67feff93fe0b27820eca0d9b61b`;
- klasifikace `active_challenge`, konkrétní signál `altcha_widget`;
- HTML obsahuje `<altcha-widget>` s atributy `auto` a `challenge` v kontejneru
  `id="altcha-gate"` v aktivní části snímků. Styl widget zmenšuje na 1 × 1 px,
  ale nevypíná jeho automatickou činnost;
- lokální inspekce uloženého kódu ukázala obsluhu události `verified`, která
  chce odeslat výsledek na archiv a znovu načíst stránku. Tento kód se
  nespouštěl a ověřovací požadavek nebyl odeslán.

Tentokrát jde o doloženou ochrannou bránu, nikoli pouhé jméno skriptu.
Po první odpovědi se operace ukončila. **Žádný další HTTP požadavek**, info.json,
obrazový snímek ani dlaždice se nestahovaly. Nedocházelo k řešení ani obcházení
Altcha, přebírání cookies či přepnutí klienta. Úspěšné živé získání úplného
obrazu a jeho skutečné rozlišení zůstávají neověřené; PR #16 proto zůstává draft.
Diagnostická odpověď, metadata a souhrn jsou v soukromém úložišti mimo Git.

### Ověření opravy

Celá sada: **118 testů, OK** (Python 3.13.5 / Pillow 11.1.0), bez produkčních
požadavků v automatických testech. Přibylo 8 testů struktury ochranných stránek
a 5 testů diagnostiky/živého toku; celkem je proti výchozím 88 testům v main
30 nových testů. Všechny obrazové podklady testů jsou syntetické.

Ověřeno pokračování při běžném odkazu na altcha/recaptcha skript, inline JS,
komentářích, textu a neaktivních šablonách; zastavení při skutečných widgetech
včetně automatického widgetu o velikosti 1 px a widgetu za prvních 64 KiB HTML.
Dále rozlišení HTML místo IIIF, zachování autoritativního HTTP stavu i při
vadném HTML, uložení diagnostiky před chybou, redakce citlivých polí a odmítnutí
přepsání či uložení do Git. Verze zůstává 0.6.0 jako oprava dosud nevydaného PR.

## Ruční browserová relace pro jeden snímek, 14. listopadu 2026

Do dosud nevydaného PR #16 doplněn samostatný příkaz
`archive mza browser-download`. Volitelný Playwright 1.65.2 spouští viditelný
Chrome/Chromium v nové dočasné relaci. Uživatel sám otevře odkaz z místní
úvodní karty, dokončí nativní ověření archivu a klikne na pokračování.
Implementace nepočítá Altcha, nepřebírá ověřovací payload, nekliká na výzvu
ani uživatelovo potvrzení. Nativní ověřovací GET/POST smí odeslat jen stránka
archivu před potvrzením; po něm jsou tyto operace blokované.

Kontrolované GET detailu, metadat a obrazu běží pomocí streamovaného `fetch`
v původní kartě a stejném BrowserContext. Cookies zpracovává browser;
neexportují se, nečtou se a nepřenášejí se do HTTP klienta. Nepoužívá se
Playwright `context.request`, persistentní profil ani cookie soubor.
Zachována kontrola TLS, veřejných IP a DNS pinning, vypnuty proxy, service
workers a WebSockety. Změna souhlasu, blokace, přesměrování, nová ochrana,
CORS nebo ztráta karty/relace operaci zastaví bez jiného klienta.

Platí stejná kontrola IIIF 2/3, omezení přenosu, rozměrů, počtu požadavků,
úplnosti a atomického importu. Prohlížeč sám rozbaluje HTTP kompresi;
velikost se kontroluje na rozbaleném toku. Browserový režim používá stejný
globální zámek jako HTTP režim. `source.acquisition.browser_session` uchová
neautentizační ID akvizice, čas ručního potvrzení a údaje o zachování relace
bez cookies; strukturu kontroluje `project check` a zachová ji ZIP.
Záznam zůstává `unread`, bez vizuální kontroly a podpořených tvrzení.
Volitelná diagnostika zaznamenává pouze kontrolované získání po potvrzení,
nikoli ověřovací provoz nebo obsah browserového úložiště.

### Skutečně provedené testy

Závěrečná sada s předepsaným Pillow a zapnutým testem skutečného browseru:

```sh
FAMILY_TREE_BROWSER_TEST=1 python3 -m unittest discover -s tests -v
```

**132 testů, 23,985 s, OK**, bez přeskočení. Prostředí: Python 3.13.5,
Pillow 13.0.0, Playwright 1.65.2, místní Google Chrome 154.0.8037.57.
Test browseru vyžaduje grafické prostředí; bez `FAMILY_TREE_BROWSER_TEST=1`
se čtyři browserové testy výslovně přeskočí, ostatní nevyžadují Playwright.

Nových je 14 testů: 10 jednotkových a čtyři s viditelným Chrome. Syntetický
archiv je celý obsloužen lokálním Playwright routingem; žádný jeho požadavek
se neposílá na produkční MZA. Syntetická stránka a její testovací ovládání
nejsou kopií ani automatizovaným řešením skutečné Altcha výzvy.

- Předčasné potvrzení při přítomném widgetu nepropustilo stažení. Po kliknutí
  na syntetické ovládání stránka nastavila HttpOnly session cookie a reloadovala.
  Kontrolované požadavky ji browser sám připojil; fixture ji ověřila na straně
  simulovaného serveru. Produktový kód ji nečetl.
- Ve stejné kartě/relaci úspěšně proběhl API 2 celý JPEG i API 3 sestava
  12 dlaždic. Výsledkem je pouze syntetický obraz **517 × 389 px**;
  `live_access_verified` zůstalo `false`.
- Skutečný Chrome odmítl CORS s jiným povoleným originem. HTTP 403 zastavilo
  získání bez nových požadavků, jiného klienta, importu nebo změny revize.
- Zrušení, timeout a zavření úvodní karty skončily chybou. Veřejný browserový
  vstup byl samostatně spuštěn a zrušen před sítí; zavřel kontext i prohlížeč
  a uložil souhrn diagnostiky s nulou odpovědí.
- Jednotkově ověřeny přesná URL a původní frame, blokace předběžného vieweru,
  povolení nativního ověřování pouze v ruční fázi, odvolání souhlasu, veřejné
  DNS, stavové zákazy, změna/zavření karty nebo kontextu, částečný timeout
  započtený do přenosu, chybná/velká data a odmítnutí fallback klienta.
- Export/obnova zachovaly browserovou provenienci; poškozená metadata se
  odmítla. Duplicitní URL a neplatný vstup neotevřely prohlížeč.

**Nový živý průchod s ručním ověřením MZA nebyl proveden.** Posledním
produkčním důkazem zůstává výše popsaná uložená Altcha brána z 09:27:52 SEČ.
Funkčnost produkčního credentialed CORS, získání plného obrazu a jeho
skutečné rozměry čekají na ruční akceptaci. PR zůstává draft.
Změny obsahují pouze obecný kód, dokumentaci a syntetické testy; skutečné
odpovědi, souhlas, cookies ani snímky nejsou součástí repozitáře.
