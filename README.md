# Family Tree for ChatGPT

Český genealogický asistent pro ChatGPT. Projekt připravuje převod postupů a nástrojů z [sarsonj/rodokmen-skill](https://github.com/sarsonj/rodokmen-skill) do prostředí ChatGPT.

Aktuální verze: **0.4.5** (13. listopadu 2026).

## Stav

Verze 0.4.5, vydaná 13. listopadu 2026. Obsahuje převedený
pracovní postup pro jeden zápis, nástroj pro výřez snímku a lokální evidenci
pramenů s historií. Ověřen je lokální export a obnova úplného stavu přes ZIP
s kontrolními součty. Živý přístup a práce s jedním snímkem byly ověřeny pro
Zemský archiv v Opavě a MZA Brno; ochranné výzvy řešil ručně uživatel. Nejde o
plugin zveřejněný ve veřejném katalogu; repozitář je ale zabalený jako lokální
skills-only plugin pro ChatGPT desktop a Codex. Přenos přes trvalé soukromé
úložiště do nové konverzace je
ověřený včetně pokračování další revizí. První skutečný zápis MZA prošel
vizuální kontrolou, přepisem, překladem a oddělenou interpretací. Implementovaný
je také bezpečný offline import GEDCOM tvrzení, plán chybějících dokladů,
výzkumná fronta předků, kontrolní obrazové deriváty a neblokující audit kvality.
Nový badatelský stav formátu 2 odděluje pracovní identity od dokazovaných
tvrzení, citací a rozporů; starší formát 1 lze výslovně migrovat. Dílčí skripty
jsou dostupné přes jedno stabilní příkazové rozhraní.
Všech 31 nástrojů původního projektu bylo funkčně roztříděno; užitečné offline
postupy byly adaptovány, zatímco síťové archivní a webové nástroje zůstávají
odložené do samostatného ověření.
Ve verzi 0.4.0 přibyl bezpečný jednosměrný adaptér pro Gramps Web
API 3.x s příkazy `probe`, `plan`, `push` a `status`. Je ověřen jednotkovými
testy i úplným syntetickým průchodem proti dočasnému oficiálnímu Gramps Web
API 3.25.2 / Gramps 6.0.8; skutečná rodinná data použita nebyla.

Zdroj postupu je ve [skills/family-tree-chatgpt](skills/family-tree-chatgpt). Přehled převodu a odložených nástrojů je v [docs/PORTING.md](docs/PORTING.md), výsledky ověření v [docs/VALIDATION.md](docs/VALIDATION.md).

## Cíl projektu

Vytvořit obecný, dohledatelný a soukromí respektující nástroj pro genealogický
výzkum v ChatGPT/Codexu: od přijetí neověřeného tvrzení přes práci s pramenem,
přepis a posouzení totožnosti až po bezpečné uložení a pokračování. Konkrétní
osoby z pilotních zápisů jsou testovací případy nástroje, nikoli výzkumný cíl
projektu.

## Novinky ve verzi 0.4.0

- append-only propojení s Gramps Web API 3.x bez přímého zápisu do databáze,
- export pouze podporovaných tvrzení mimo otevřené konflikty,
- mapování osob, jmen, vybraných událostí, rodičovské vazby, pramenů, citací a
  výzkumných poznámek,
- soukromý plán opatřený SHA-256 s kontrolou serveru, stromu, revize a stavu,
- odmítnutí mazání, vzdálených aktualizací, kolizí a nešifrovaného připojení,
- přenosný Agent Plugins 1.0 manifest, kompatibilní manifest pro Codex a
  repozitářový marketplace pro instalaci v ChatGPT desktop,
- automatická kontrola shody vydané verze, obou manifestů a marketplace.

## Novinky ve verzi 0.4.5

- samostatný append-only tok `gramps tasks probe/plan/push` pro standardní
  soukromé úkoly na obrazovce Tasks v Gramps Web,
- explicitní vstupní JSON úkolů, stabilní identifikátory a automatické
  zajištění tagu `ToDo`,
- opakovaný push bez duplicit a bez přepisování stavu, priority, titulu nebo
  popisu, které uživatel následně upravil v Gramps Web.

## Novinky ve verzi 0.3.0

- obecný model osob, vztahů, tvrzení, pramenů a explicitních konfliktů,
- badatelský stav formátu 2 s kontrolou odkazů, citací a souborů pramenů,
- atomické modelové změny a bezpečné řešení rozporů bez mazání původních tvrzení,
- výslovná migrace formátu 1 při zachování historie a kompatibility exportu,
- jednotné CLI `family_tree.py` pro projekt, zápisy, model, GEDCOM a obrázky,
- rozšířená sada 44 syntetických testů.

## Novinky ve verzi 0.2.0

- bezpečný offline import GEDCOM včetně konzervativní fronty předků,
- kontrolní obrazové deriváty pro čtení a porovnávání zápisů,
- neblokující audit kvality badatelského stavu,
- úplný funkční audit 31 nástrojů původního projektu a adaptace užitečných
  offline postupů,
- doplněná metodika, dokumentace bezpečnosti a rozšířená sada 38 testů.

## Splněný milník 0.1.0

Z jednoho skutečného matričního zápisu vytvořit dohledatelný badatelský výsledek:

1. Přijmout snímek nebo odkaz na zápis.
2. Získat a vizuálně ověřit čitelný snímek; první pilot zaměřit na Zemský archiv v Opavě.
3. Uložit archivní citaci, odkaz, označení knihy a strany/snímku.
4. Odděleně připravit přepis originálu, český překlad a interpretaci.
5. Evidovat nejistá čtení, hypotézy a důvody případného ztotožnění osob.
6. Uložit stav a badatelský deník tak, aby šlo navázat v další konverzaci.

Milník je splněný až po doloženém průchodu všemi kroky a ověření navázání v nové konverzaci.

## Plán

- [x] Vytvořit katalog původních nástrojů, vybrat minimum a ověřit jeho závislosti a licenci.
- [x] Převést základní pracovní postup pro ChatGPT a odstranit závislosti na Claude.
- [x] Vybrat a lokálně otestovat minimum pro první zápis na syntetických datech.
- [x] Ověřit přístup k Opavskému archivu a práci se snímkem.
- [x] Ověřit přístup k MZA a bezpečný výřez z browserového screenshotu.
- [x] Navrhnout a lokálně vyzkoušet přenosový balíček celého badatelského stavu.
- [x] Uložit balíček do trvalého soukromého úložiště a obnovit jej v nové konverzaci.
- [x] Dokončit první ověřený průchod a kontrolu navázání.
- [x] Přidat import GEDCOM a plán dohledání dokladů.
- [x] Porovnat všech 31 upstream nástrojů a adaptovat kontrolu obrazů, audit
  kvality, frontu předků a metodiku ověřování.
- [x] Navrhnout obecný model osob, vztahů, tvrzení, pramenů a konfliktů.
- [x] Sjednotit dílčí skripty pod jedno stabilní příkazové rozhraní.
- [x] Posoudit Gramps Web a implementovat bezpečný jednosměrný adaptér.
- [ ] Posoudit samostatný rodinný web a případnou obousměrnou synchronizaci.

## Kvalita bádání

- Přepisovat pouze to, co je skutečně čitelné na snímku; nejistá místa a mezery označit.
- Rozlišovat obsah pramene od badatelské interpretace.
- Přečtený zápis sám o sobě nedokazuje totožnost osoby ani příbuzenskou vazbu.
- Neslučovat osoby jen podle shodného jména a přibližného data.
- Uchovávat citace a zaznamenávat i neúspěšná hledání včetně prohledaného rozsahu.
- Respektovat limity archivů, používat mezipaměť a neobcházet blokace.

## Lokální použití

Vyžaduje Python 3.11+ a pro obrazové nástroje Pillow. Testováno na kombinacích
Python 3.12.14 / Pillow 13.0.0 a Python 3.13.5 / Pillow 11.1.0. Projektové,
modelové, GEDCOM a Gramps příkazy používají pouze standardní knihovnu Pythonu;
Pillow se načítá až pro obrazové příkazy.

### Instalace pluginu v ChatGPT desktop

Z kořene repozitáře přidej místní marketplace a nainstaluj plugin:

```sh
codex plugin marketplace add .
codex plugin add family-tree-chatgpt@family-tree-chatgpt
```

Příkazy vyžadují Codex CLI dostupné v `PATH`; stejnou instalaci lze provést
také přes správu pluginů v ChatGPT desktop.
Potom restartuj ChatGPT desktop a otevři novou konverzaci. Marketplace načítá
plugin přímo z kořene repozitáře; soukromá badatelská data zůstávají mimo Git.
Po změně zdrojů spusť znovu instalaci pluginu a ověř novou konverzaci.

### Přímé spuštění CLI

```sh
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
python3 skills/family-tree-chatgpt/scripts/family_tree.py --workspace /cesta/mimo/repozitar/soukrome-badani project init
python3 skills/family-tree-chatgpt/scripts/family_tree.py --workspace /cesta/mimo/repozitar/soukrome-badani project resume
python3 skills/family-tree-chatgpt/scripts/family_tree.py --workspace /cesta/mimo/repozitar/soukrome-badani project audit
python3 skills/family-tree-chatgpt/scripts/family_tree.py --workspace /cesta/mimo/repozitar/soukrome-badani model apply /soukrome-uloziste/zmena-modelu.json --expected-revision 0 --next-step "Ověřit první tvrzení."
python3 skills/family-tree-chatgpt/scripts/family_tree.py --workspace /cesta/mimo/repozitar/soukrome-badani project export /soukrome-uloziste/badani.zip
python3 skills/family-tree-chatgpt/scripts/family_tree.py --workspace /nova/cesta/obnovene-badani project restore /soukrome-uloziste/badani.zip
python3 skills/family-tree-chatgpt/scripts/family_tree.py gedcom import /soukrome-uloziste/strom.ged /soukrome-uloziste/strom-import.json
python3 skills/family-tree-chatgpt/scripts/family_tree.py gramps probe --url https://rodokmen.example.cz --username editor
python3 skills/family-tree-chatgpt/scripts/family_tree.py --workspace /cesta/mimo/repozitar/soukrome-badani gramps plan /soukrome-uloziste/gramps-plan.json --url https://rodokmen.example.cz --username editor
python3 skills/family-tree-chatgpt/scripts/family_tree.py --workspace /cesta/mimo/repozitar/soukrome-badani gramps push /soukrome-uloziste/gramps-plan.json --url https://rodokmen.example.cz --username editor
python3 skills/family-tree-chatgpt/scripts/family_tree.py gramps tasks probe --url https://rodokmen.example.cz --username editor
python3 skills/family-tree-chatgpt/scripts/family_tree.py gramps tasks plan /soukrome-uloziste/ukoly.json /soukrome-uloziste/gramps-task-plan.json --url https://rodokmen.example.cz --username editor
python3 skills/family-tree-chatgpt/scripts/family_tree.py gramps tasks push /soukrome-uloziste/gramps-task-plan.json --url https://rodokmen.example.cz --username editor
python3 skills/family-tree-chatgpt/scripts/family_tree.py image split /soukrome-uloziste/snimky/scan.png /soukrome-uloziste/snimky/left.png /soukrome-uloziste/snimky/right.png
```

Cesta je příklad; zvol vlastní soukromou složku mimo git repozitáře. Další
příkazy a formát zápisu jsou v [datové referenci](skills/family-tree-chatgpt/references/data.md),
obecné entity a konflikty v [referenci modelu](skills/family-tree-chatgpt/references/model.md)
a GEDCOM i Gramps Web v samostatných návodech
[GEDCOM](skills/family-tree-chatgpt/references/gedcom.md) a
[Gramps](skills/family-tree-chatgpt/references/gramps.md).
Skripty samy nečtou písmo, neověřují totožnost osoby a neprovádějí cloudové
ukládání. Importovaný GEDCOM je veden jako soubor neověřených tvrzení, nikoli
jako archivní důkaz, a bez vědomého mapování nemění obecný model. Gramps export
je jednosměrný, append-only a ponechává `research.json` jako autoritativní stav.

## Kód a rodinná data

Tento repozitář slouží pro obecné návody, kód a syntetická testovací data. Rodinné GEDCOM soubory, originální dokumenty, snímky, přepisy a badatelské deníky patří do samostatného soukromého úložiště. Pravidla v `.gitignore` jsou pouze pomocná; před commitem je nutné zkontrolovat jeho obsah.

## Původ projektu a licence

Výchozím projektem je **Rodokmen** od **Jindřicha Šaršona**, zveřejněný pod licencí MIT. Při převzetí kódu nebo podstatných částí dokumentace je nutné přiložit úplné původní licenční a autorské oznámení a zaznamenat původ převzatých souborů.

Referenční revize je `0fb0c0379abf51a9af92d363992799fcd38eb23a`. Mapování adaptovaných částí je v [přehledu původu](skills/family-tree-chatgpt/references/upstream.md); úplné původní MIT oznámení je v [LICENSE](LICENSE) a přiložené také k samotnému balíčku.
