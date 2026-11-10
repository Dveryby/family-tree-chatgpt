# Family Tree for ChatGPT

Český genealogický asistent pro ChatGPT. Projekt připravuje převod postupů a nástrojů z [sarsonj/rodokmen-skill](https://github.com/sarsonj/rodokmen-skill) do prostředí ChatGPT.

## Stav

První lokální prototyp, 10. listopadu 2026. Obsahuje převedený pracovní postup pro jeden zápis, nástroj pro výřez snímku a lokální evidenci pramenů s historií. Nejde o publikovaný plugin. Živý přístup k archivům, GEDCOM a přenos soukromého bádání přes trvalé úložiště do nové konverzace ještě nejsou ověřené.

Zdroj postupu je ve [skills/family-tree-chatgpt](skills/family-tree-chatgpt). Přehled převodu a odložených nástrojů je v [docs/PORTING.md](docs/PORTING.md), výsledky ověření v [docs/VALIDATION.md](docs/VALIDATION.md).

## Cíl první verze

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
- [ ] Ověřit přístup k Opavskému archivu a práci se snímkem.
- [ ] Navrhnout a vyzkoušet trvalé ukládání rozpracovaného bádání.
- [ ] Dokončit první ověřený průchod a kontrolu navázání.
- [ ] Přidat import GEDCOM a plán dohledání dokladů.
- [ ] Později posoudit propojení s Gramps Web a rodinný web.

## Kvalita bádání

- Přepisovat pouze to, co je skutečně čitelné na snímku; nejistá místa a mezery označit.
- Rozlišovat obsah pramene od badatelské interpretace.
- Přečtený zápis sám o sobě nedokazuje totožnost osoby ani příbuzenskou vazbu.
- Neslučovat osoby jen podle shodného jména a přibližného data.
- Uchovávat citace a zaznamenávat i neúspěšná hledání včetně prohledaného rozsahu.
- Respektovat limity archivů, používat mezipaměť a neobcházet blokace.

## Lokální použití

Vyžaduje Python 3.11+ a pro výřezy Pillow. Testované prostředí: Python 3.12.14 a Pillow 13.0.0. Příkazy pro zápisník používají pouze standardní knihovnu Pythonu.

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python skills/family-tree-chatgpt/scripts/research.py --workspace /cesta/mimo/repozitar/soukrome-badani init
python skills/family-tree-chatgpt/scripts/research.py --workspace /cesta/mimo/repozitar/soukrome-badani resume
```

Cesta je příklad; zvol vlastní soukromou složku mimo git repozitáře. Další příkazy a formát záznamu jsou v [datové referenci](skills/family-tree-chatgpt/references/data.md). Skripty samy nečtou písmo, neověřují totožnost osoby a neprovádějí cloudové ukládání. Kontrola dat není důkazem správného genealogického závěru.

## Kód a rodinná data

Tento repozitář slouží pro obecné návody, kód a syntetická testovací data. Rodinné GEDCOM soubory, originální dokumenty, snímky, přepisy a badatelské deníky patří do samostatného soukromého úložiště. Pravidla v `.gitignore` jsou pouze pomocná; před commitem je nutné zkontrolovat jeho obsah.

## Původ projektu a licence

Výchozím projektem je **Rodokmen** od **Jindřicha Šaršona**, zveřejněný pod licencí MIT. Při převzetí kódu nebo podstatných částí dokumentace je nutné přiložit úplné původní licenční a autorské oznámení a zaznamenat původ převzatých souborů.

Referenční revize je `0fb0c0379abf51a9af92d363992799fcd38eb23a`. Mapování adaptovaných částí je v [přehledu původu](skills/family-tree-chatgpt/references/upstream.md); úplné původní MIT oznámení je v [LICENSE](LICENSE) a přiložené také k samotnému balíčku.
