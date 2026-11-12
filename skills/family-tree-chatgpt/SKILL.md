---
name: family-tree-chatgpt
description: >-
  Český genealogický pracovní postup pro čtení jednoho matričního zápisu,
  přepis a překlad snímku, evidenci pramenů, posouzení totožnosti osob,
  import neověřených GEDCOM tvrzení a navázání na rozpracované bádání. Použij
  při dotazech na rodokmen, předky a matriky, pokud uživatel dodá snímek, odkaz,
  GEDCOM nebo existující badatelský stav. Nezajišťuje automatické procházení
  archivů, správu Gramps ani rodinný web.
---

# Rodokmen pro ChatGPT

## Načíst stav a určit cíl

1. Určit konkrétní otázku: co se má přečíst nebo kterou vazbu máme ověřit.
   Nevyžadovat nový rodinný rozhovor, pokud zadání a podklady stačí.
2. Při pokračování načíst aktuální soukromý badatelský stav a související snímky.
   Použít `scripts/research.py --workspace <soukromá-složka> resume`.
   Projít relevantní záznamy a události; nezačínat pouze podle paměti chatu.
3. Není-li stav dostupný, dohledat jej v autorizovaném soukromém úložišti.
   Chybějící data nebo snímky přiznat. Nerekonstruovat je jako fakta z paměti.
4. Pro nový případ založit pracovní složku mimo repozitář kódu:
   `python scripts/research.py --workspace <soukromá-složka> init`.
   Použít Python 3.11+. Složka obsahuje pouze lokální pracovní kopii,
   dokud ji skutečně neuložíš do trvalého soukromého úložiště.

## Importovat GEDCOM jako neověřená tvrzení

1. Číst [návod GEDCOM](references/gedcom.md). Vstupní `.ged` i výstupní JSON
   musí zůstat v soukromé složce mimo Git.
2. Spustit `python3 scripts/gedcom.py <strom.ged> <nový-výstup.json>`. Nástroj
   vstup nemění a odmítne přepsat existující výstup.
3. Zkontrolovat `warnings` a `research_plan`. Neznámé rozšíření se zachovává,
   ale není automaticky interpretováno.
   Je-li známá výchozí osoba, přidat `--root @ID@`; soukromý výstup pak obsahuje
   Kekulého pozice a výzkumnou frontu předků. Vazby i navržené výchozí události
   zůstávají neověřenými tvrzeními.
4. Osoby, vztahy, data a prameny z GEDCOM vést jako `unverified_claims`.
   Nezaměňovat přítomnost `SOUR` za vizuální ověření původního pramene.
5. Podle `research_plan` postupně získávat skutečné doklady. Ověřený matriční
   zápis ukládat přes `research.py`; GEDCOM import sám `research.json` nemění.

## Otevřít a identifikovat pramen

1. U přiloženého snímku ověřit, zda je čitelné celé relevantní místo včetně záhlaví,
   okolních řádků, poznámek na okraji a případného pokračování na další straně.
2. U odkazu zjistit dostupné připojené nástroje. Pokud umožní potřebnou akci,
   použít je; pro interaktivní prohlížeč dodržet jeho aktuální instrukce.
   Nevymýšlet názvy nástrojů a nepředpokládat přítomnost Playwrightu.
3. Pro Opavu přečíst [postup a omezení](references/opava.md), pro MZA
   [samostatný postup](references/mza.md). Zde není síťový stahovač.
4. Před čtením ověřit na stránce archiv, fond/sbírku, signaturu, obec/farnost,
   rozsah let, druh knihy, stranu a číslo snímku. Rozlišovat rok knihy a rok události.
5. Zapsat citaci a přesný skutečně zjištěný odkaz. Chybějící údaj označit jako chybějící.
   Citaci ani adresu snímku nevymýšlet. Právní dostupnost mladších údajů případně
   ověřit v aktuálních oficiálních podkladech, neodvozovat ji jen ze stáří svazku.
6. Pokud zdroj nelze otevřít, uložit událost `blocked` a důvod. Můžeš dále
   číst dodaný snímek, ale neoznačovat výsledek za ověřený v archivním prohlížeči.

## Připravit snímek a přečíst zápis

1. Zachovat původní soubor beze změny ve `sources/` soukromé pracovní složky.
2. Pro obyčejný výřez použít `scripts/crop.py <originál> <výstup.png> --box x0,y0,x1,y1`.
   Souřadnice jsou zlomky 0–1 po EXIF orientaci. Výřez zahrnout velkoryse.
   Potřeba je Pillow; podrobnosti jsou v [referenci dat](references/data.md).
3. Vizuálně prohlédnout originál i výřez skutečným nástrojem pro obrázky.
   Skript pouze ořezává; nečte písmo a nepotvrzuje správnost přepisu.
   Pro široký zápis lze použít `scripts/image_review.py split`, pro kontrolu
   rozsahu `mark` a pro přehled několika již uložených snímků `sheet`. Tyto
   režimy pracují pouze s místními soubory a vytvářejí deriváty mimo Git;
   kontrastní kopie nikdy nenahrazuje originál.
4. Přepisovat originální znění. Nejisté čtení označit `(?)`, nečitelné místo `[…]`.
   Neodhadovat jméno podle očekávaného předka. Nepoužívat generativní opravy písma.
5. Překlad do češtiny držet zvlášť; zachovat význam, nejasnosti a původní míru jistoty.
6. V interpretaci vysvětlit, co lze ze zápisu vyvodit, včetně rozporů a alternativ.
   Rozlišovat datum narození/křtu, sňatku/ohlášek a úmrtí/pohřbu.

## Posoudit totožnost osoby samostatně

Při spojování generací, rozporech nebo mrtvém bodu číst
[metodiku ověřování](references/methodology.md).

- Hledat souvislost v rodičích, partnerovi, čísle domu, obci, povolání a chronologii;
  ověřit také stejně pojmenované kandidáty, další sňatky a možné přestěhování.
- Shodu jména a přibližné doby vést jako vodítko. Sama nestačí pro příbuzenskou vazbu.
- Vést stav čtení (`unread`, `draft`, `reviewed`) odděleně od totožnosti
  (`unresolved`, `supported`, `rejected`). `reviewed` znamená vizuální kontrolu
  zápisu, nikoli důkaz totožnosti, bezchybného čtení ani pravdivosti údaje.
- U závěru o totožnosti uvést citované podklady, důvody a otevřené rozpory.
  Neměnit nejistotu na fakt jen podle uživatelovy preference.
- Rodinné podání a cizí rodokmeny označit jako převzatá tvrzení, nikoli matriční doklad.

## Uložit výsledek a umožnit navázání

1. Připravit záznam podle `assets/record.json`; číst [datovou referenci](references/data.md).
   V soukromé složce vyplnit přepis, překlad, interpretaci, nejistoty a citaci.
2. Načíst poslední `revision` pomocí `resume`. Pro změnu použít:
   `python scripts/research.py --workspace <složka> put <záznam.json> --expected-revision <n> --next-step "Konkrétní další krok"`.
   Změna obsahuje celý jeden záznam; ostatní záznamy zůstanou zachované a předchozí stav se zálohuje.
3. Negativní hledání nebo blokaci uložit příkazem `log` s `--result not_found|blocked|note`,
   `--scope "Kniha, roky, snímky a dotaz"`, `--expected-revision <n>` a `--next-step`.
4. Spustit `check`. Kontrola ověřuje strukturu, citace pro `reviewed`, SHA-256 snímků
   a explicitní důvody ztotožnění. Nepotvrzuje paleografickou či historickou správnost.
   Potom spustit `audit`; ten nemění stav a vypíše neblokující varování, například
   chybějící překlad či interpretaci, otevřené nejistoty nebo stejnou citaci u
   více záznamů. Varování posoudit věcně, neodstraňovat je mechanicky.
5. Při změně revize načíst stav znovu a věcně spojit změny. Při změně kontrolního součtu
   nejprve vyšetřit rozdíl, neoznačit nový soubor automaticky za původní.
6. Před přenosem spustit `check` a vytvořit balíček příkazem
   `research.py --workspace <složka> export <výstup.zip>`. Výstup musí být mimo
   badatelskou složku i git repozitář. Uchovat vrácený SHA-256; podrobnosti jsou
   v [datové referenci](references/data.md).
7. Balíček uložit do uživatelem určeného trvalého soukromého úložiště. Lokální
   skript jej nenahrává ani nešifruje; přístupová práva a přenos řeší zvolené úložiště.
8. Při navázání obnovit balíček příkazem `restore` do nové neexistující složky,
   znovu spustit `check` a `resume` a porovnat revizi, další krok a kontrolní součty.
9. Potvrdit trvalé uložení až po úspěšném zápisu a zpětném ověření. Jinak říci,
   že stav zůstává pouze v pracovní kopii. Neslibovat navázání závislé na
   neuložených souborech.
10. Stručně shrnout zjištění, nejistoty, zdroj a další krok. Zobrazit relevantní výřez,
   pokud je dostupný a prostředí to podporuje. Nezveřejňovat soukromá data v repozitáři.

## Respektovat archiv a rozsah

- Na jednom archivu pracovat postupně a bez souběžného listování. Použít uložené snímky.
- Při blokaci nebo CAPTCHA nepřidávat alternativní síťové cesty. Řídit se pokyny nástroje;
  pokud je nutná akce uživatele, předat pouze potřebný krok.
- Bez dostupného pramene nehlásit dohledání. Odhad a hypotézu vždy označit.
- Gramps, hromadné hledání, graf osob a web jsou mimo tuto první verzi.
  U takového požadavku pojmenovat chybějící funkci a udělat dostupnou část práce.

Původ adaptace a úplná licence: [references/upstream.md](references/upstream.md), `LICENSE`.
