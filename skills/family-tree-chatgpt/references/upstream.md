# Původ a rozsah adaptace

- Autor původního projektu: Jindřich Šaršon.
- Repozitář: https://github.com/sarsonj/rodokmen-skill.
- Referenční revize: `0fb0c0379abf51a9af92d363992799fcd38eb23a`.
- Licence: MIT, úplné původní oznámení je v přiloženém souboru `LICENSE`.
- Adaptace v této verzi: Family Tree for ChatGPT, 10. listopadu 2026.

| Původní soubor v `skills/rodokmen/` | Zdejší soubor | Změna |
|---|---|---|
| `SKILL.md` | `SKILL.md` | Zúžený pracovní postup pro jeden zápis; dostupné nástroje ChatGPT, samostatný stav čtení a totožnosti, žádné Claude hooky/modely ani instalace systémových programů |
| `reference/portaly.md`, oddíl ZA Opava | `references/opava.md` | Konzervativní pilotní postup, bez interních síťových volání a bez tvrzení o živé funkčnosti |
| `tools/vyrez.py` | `scripts/crop.py` | Normalizované souřadnice; Pillow místo ImageMagicku, explicitní výstup mimo repo, PNG, zákaz přepsání a SHA-256 |

`scripts/research.py`, datová šablona a testy jsou nová implementace pro tuto verzi;
nejsou převodem původního formátu `osoby.py` ani původního `zapis.py`.
Původní strom a jeho JSON soubory nejsou s tímto schématem automaticky kompatibilní.
Úplné původní zdrojové soubory nejsou do balíčku kopírované.
