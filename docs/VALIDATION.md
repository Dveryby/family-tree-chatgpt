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
- Přístup k Opavskému archivu, CAPTCHA, stažení skutečného snímku a dohledání knihy.
- Uložení celé soukromé složky do trvalého úložiště a obnovení v nové uživatelské konverzaci.
- Funkčnost na Windows/macOS či Pythonu 3.11; vyzkoušeno bylo uvedené linuxové prostředí.
- GEDCOM, Gramps, automatické hledání, původní databázové schéma a web.

První projektový milník se skutečným pramenem proto zůstává otevřený.
