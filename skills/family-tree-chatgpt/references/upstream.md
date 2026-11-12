# Původ a rozsah adaptace

- Autor původního projektu: Jindřich Šaršon.
- Repozitář: https://github.com/sarsonj/rodokmen-skill.
- Referenční revize: `0fb0c0379abf51a9af92d363992799fcd38eb23a`.
- Licence: MIT, úplné původní oznámení je v přiloženém souboru `LICENSE`.
- Adaptace a funkční audit ve verzi 0.2.0: Family Tree for ChatGPT,
  10.–12. listopadu 2026.

| Původní soubor v `skills/rodokmen/` | Zdejší soubor | Změna |
|---|---|---|
| `SKILL.md` | `SKILL.md` | Zúžený pracovní postup pro jeden zápis; dostupné nástroje ChatGPT, samostatný stav čtení a totožnosti, žádné Claude hooky/modely ani instalace systémových programů |
| `reference/portaly.md`, oddíl ZA Opava | `references/opava.md` | Konzervativní pilotní postup, bez interních síťových volání a bez tvrzení o živé funkčnosti |
| `reference/metodika.md`, `reference/matriky.md` | `references/methodology.md` | Zkrácená metodika pramenů, ztotožnění, hledání a mrtvých bodů; bez proměnlivých právních lhůt a Claude/ImageMagick pokynů |
| `tools/vyrez.py` | `scripts/crop.py` | Normalizované souřadnice; Pillow místo ImageMagicku, explicitní výstup mimo repo, PNG, zákaz přepsání a SHA-256 |
| `tools/overit.py` | `scripts/image_review.py split` | Dvě překrývající se části pro kontrolu čtení; Pillow, soukromé PNG, volitelný pracovní kontrast, bez ImageMagicku |
| `tools/ramecek.py` | `scripts/image_review.py mark` | Označený náhled s více rámečky; bez vazby na upstreamový `zvyrazneni.json` |
| `tools/mapa_knihy.py`, režim `soubory` | `scripts/image_review.py sheet` | Pouze montáž již uložených místních snímků; síťové režimy archivů nejsou převzaté |
| `tools/kontrola.py` | `scripts/research.py audit` | Převzaté rozlišení chyb a varování; kontroly kompletně přepsané pro JSON schéma této verze |
| `tools/ged_import.py`, fronta předků | `scripts/gedcom.py --root` | Adaptované Kekulého pozice a pořadí ověřování; nový parser, neověřená tvrzení, cykly a více rodičovských rodin se řeší konzervativně |

`scripts/research.py`, datová šablona a testy jsou nová implementace pro tuto verzi;
nejsou převodem původního formátu `osoby.py` ani původního `zapis.py`.
Také základ `scripts/gedcom.py` je nová implementace podle veřejné specifikace
GEDCOM; původní parser ani jeho datový model nebyly převzaty. Volitelná fronta
předků ale výslovně adaptuje užitečný pracovní postup původního nástroje.
Původní strom a jeho JSON soubory nejsou s tímto schématem automaticky kompatibilní.
Úplné původní zdrojové soubory nejsou do balíčku kopírované.
