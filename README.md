# Family Tree for ChatGPT

Český genealogický asistent pro ChatGPT. Projekt připravuje převod postupů a nástrojů z [sarsonj/rodokmen-skill](https://github.com/sarsonj/rodokmen-skill) do prostředí ChatGPT.

Aktuální verze: **0.2.0** (12. listopadu 2026).

## Stav

Minor verze 0.2.0, aktualizovaná 12. listopadu 2026. Obsahuje převedený
pracovní postup pro jeden zápis, nástroj pro výřez snímku a lokální evidenci
pramenů s historií. Ověřen je lokální export a obnova úplného stavu přes ZIP
s kontrolními součty. Živý přístup a práce s jedním snímkem byly ověřeny pro
Zemský archiv v Opavě a MZA Brno; ochranné výzvy řešil ručně uživatel. Nejde o
publikovaný plugin. Přenos přes trvalé soukromé úložiště do nové konverzace je
ověřený včetně pokračování další revizí. První skutečný zápis MZA prošel
vizuální kontrolou, přepisem, překladem a oddělenou interpretací. Implementovaný
je také bezpečný offline import GEDCOM tvrzení, plán chybějících dokladů,
výzkumná fronta předků, kontrolní obrazové deriváty a neblokující audit kvality.
Všech 31 nástrojů původního projektu bylo funkčně roztříděno; užitečné offline
postupy byly adaptovány, zatímco síťové a webové nástroje zůstávají odložené
do samostatného ověření.

Zdroj postupu je ve [skills/family-tree-chatgpt](skills/family-tree-chatgpt). Přehled převodu a odložených nástrojů je v [docs/PORTING.md](docs/PORTING.md), výsledky ověření v [docs/VALIDATION.md](docs/VALIDATION.md).

## Cíl projektu

Vytvořit obecný, dohledatelný a soukromí respektující nástroj pro genealogický
výzkum v ChatGPT/Codexu: od přijetí neověřeného tvrzení přes práci s pramenem,
přepis a posouzení totožnosti až po bezpečné uložení a pokračování. Konkrétní
osoby z pilotních zápisů jsou testovací případy nástroje, nikoli výzkumný cíl
projektu.

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
- [ ] Navrhnout obecný model osob, vztahů, tvrzení, pramenů a konfliktů.
- [ ] Sjednotit dílčí skripty pod jedno stabilní příkazové rozhraní.
- [ ] Později posoudit propojení s Gramps Web a rodinný web.

## Kvalita bádání

- Přepisovat pouze to, co je skutečně čitelné na snímku; nejistá místa a mezery označit.
- Rozlišovat obsah pramene od badatelské interpretace.
- Přečtený zápis sám o sobě nedokazuje totožnost osoby ani příbuzenskou vazbu.
- Neslučovat osoby jen podle shodného jména a přibližného data.
- Uchovávat citace a zaznamenávat i neúspěšná hledání včetně prohledaného rozsahu.
- Respektovat limity archivů, používat mezipaměť a neobcházet blokace.

## Lokální použití

Vyžaduje Python 3.11+ a pro obrazové nástroje Pillow. Testováno na kombinacích
Python 3.12.14 / Pillow 13.0.0 a Python 3.13.5 / Pillow 11.1.0. Příkazy pro
zápisník používají pouze standardní knihovnu Pythonu.

```sh
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
python3 skills/family-tree-chatgpt/scripts/research.py --workspace /cesta/mimo/repozitar/soukrome-badani init
python3 skills/family-tree-chatgpt/scripts/research.py --workspace /cesta/mimo/repozitar/soukrome-badani resume
python3 skills/family-tree-chatgpt/scripts/research.py --workspace /cesta/mimo/repozitar/soukrome-badani audit
python3 skills/family-tree-chatgpt/scripts/research.py --workspace /cesta/mimo/repozitar/soukrome-badani export /soukrome-uloziste/badani.zip
python3 skills/family-tree-chatgpt/scripts/research.py --workspace /nova/cesta/obnovene-badani restore /soukrome-uloziste/badani.zip
python3 skills/family-tree-chatgpt/scripts/gedcom.py /soukrome-uloziste/strom.ged /soukrome-uloziste/strom-import.json
python3 skills/family-tree-chatgpt/scripts/image_review.py split /soukrome-uloziste/snimky/scan.png /soukrome-uloziste/snimky/left.png /soukrome-uloziste/snimky/right.png
```

Cesta je příklad; zvol vlastní soukromou složku mimo git repozitáře. Další příkazy a formát záznamu jsou v [datové referenci](skills/family-tree-chatgpt/references/data.md), GEDCOM v [samostatném návodu](skills/family-tree-chatgpt/references/gedcom.md). Skripty samy nečtou písmo, neověřují totožnost osoby a neprovádějí cloudové ukládání. Importovaný GEDCOM je veden jako soubor neověřených tvrzení, nikoli jako archivní důkaz.

## Kód a rodinná data

Tento repozitář slouží pro obecné návody, kód a syntetická testovací data. Rodinné GEDCOM soubory, originální dokumenty, snímky, přepisy a badatelské deníky patří do samostatného soukromého úložiště. Pravidla v `.gitignore` jsou pouze pomocná; před commitem je nutné zkontrolovat jeho obsah.

## Původ projektu a licence

Výchozím projektem je **Rodokmen** od **Jindřicha Šaršona**, zveřejněný pod licencí MIT. Při převzetí kódu nebo podstatných částí dokumentace je nutné přiložit úplné původní licenční a autorské oznámení a zaznamenat původ převzatých souborů.

Referenční revize je `0fb0c0379abf51a9af92d363992799fcd38eb23a`. Mapování adaptovaných částí je v [přehledu původu](skills/family-tree-chatgpt/references/upstream.md); úplné původní MIT oznámení je v [LICENSE](LICENSE) a přiložené také k samotnému balíčku.
