# Family Tree for ChatGPT

Český genealogický asistent pro ChatGPT. Projekt připravuje převod postupů a nástrojů z [sarsonj/rodokmen-skill](https://github.com/sarsonj/rodokmen-skill) do prostředí ChatGPT.

## Stav

Založeno 10. listopadu 2026. Zatím jde o přípravu projektu, nikoli funkční nebo nainstalovaný skill či plugin. Přístup k archivům a kompatibilita původních skriptů dosud nejsou ověřené v cílovém prostředí.

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

- [ ] Inventarizovat původní návody, skripty, závislosti a licence.
- [ ] Převést základní pracovní postup pro ChatGPT a odstranit závislosti na Claude.
- [ ] Vybrat a otestovat minimální sadu nástrojů pro první zápis.
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

## Kód a rodinná data

Tento repozitář slouží pro obecné návody, kód a syntetická testovací data. Rodinné GEDCOM soubory, originální dokumenty, snímky, přepisy a badatelské deníky patří do samostatného soukromého úložiště. Pravidla v `.gitignore` jsou pouze pomocná; před commitem je nutné zkontrolovat jeho obsah.

## Původ projektu a licence

Výchozím projektem je **Rodokmen** od **Jindřicha Šaršona**, zveřejněný pod licencí MIT. Při převzetí kódu nebo podstatných částí dokumentace je nutné přiložit úplné původní licenční a autorské oznámení a zaznamenat původ převzatých souborů.

V tomto úvodním commitu není původní kód ani dokumentace zkopírovaná. Referenční revize a rozsah převzatých částí budou uvedeny při jejich importu.
