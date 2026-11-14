---
name: family-tree-chatgpt
description: >-
  Český genealogický pracovní postup pro čtení jednoho matričního zápisu,
  přepis a překlad snímku, evidenci pramenů, posouzení totožnosti osob,
  správu osob, vztahů, tvrzení a konfliktů, import neověřených GEDCOM tvrzení,
  import a oprávněné získání jednotlivých snímků MZA s původem a kontrolou integrity
  a jednosměrný export podporovaných tvrzení do Gramps Web. Použij
  při dotazech na rodokmen, předky a matriky, pokud uživatel dodá snímek, odkaz,
  GEDCOM nebo existující badatelský stav. Nezajišťuje automatické procházení
  archivů, obousměrnou synchronizaci Gramps ani rodinný web.
---

# Rodokmen pro ChatGPT

## Načíst stav a určit cíl

1. Určit konkrétní otázku: co se má přečíst nebo kterou vazbu máme ověřit.
   Nevyžadovat nový rodinný rozhovor, pokud zadání a podklady stačí.
2. Při pokračování načíst aktuální soukromý badatelský stav a související snímky.
   Použít `scripts/family_tree.py --workspace <soukromá-složka> project resume`.
   Projít relevantní záznamy a události; nezačínat pouze podle paměti chatu.
3. Není-li stav dostupný, dohledat jej v autorizovaném soukromém úložišti.
   Chybějící data nebo snímky přiznat. Nerekonstruovat je jako fakta z paměti.
4. Pro nový případ založit pracovní složku mimo repozitář kódu:
   `python3 scripts/family_tree.py --workspace <soukromá-složka> project init`.
   Použít Python 3.11+. Složka obsahuje pouze lokální pracovní kopii,
   dokud ji skutečně neuložíš do trvalého soukromého úložiště.

## Importovat GEDCOM jako neověřená tvrzení

1. Číst [návod GEDCOM](references/gedcom.md). Vstupní `.ged` i výstupní JSON
   musí zůstat v soukromé složce mimo Git.
2. Spustit `python3 scripts/family_tree.py gedcom import <strom.ged> <nový-výstup.json>`. Nástroj
   vstup nemění a odmítne přepsat existující výstup.
3. Zkontrolovat `warnings` a `research_plan`. Neznámé rozšíření se zachovává,
   ale není automaticky interpretováno.
   Je-li známá výchozí osoba, přidat `--root @ID@`; soukromý výstup pak obsahuje
   Kekulého pozice a výzkumnou frontu předků. Vazby i navržené výchozí události
   zůstávají neověřenými tvrzeními.
4. Osoby, vztahy, data a prameny z GEDCOM vést jako `unverified_claims`.
   Nezaměňovat přítomnost `SOUR` za vizuální ověření původního pramene.
5. Podle `research_plan` postupně získávat skutečné doklady. Ověřený matriční
   zápis ukládat přes jednotné CLI; GEDCOM import sám `research.json` nemění a
   osoby neslučuje. Pro vědomé zanesení údajů do obecného modelu číst
   [referenci modelu](references/model.md) a uchovat stav `unverified`.

## Otevřít a identifikovat pramen

1. U přiloženého snímku ověřit, zda je čitelné celé relevantní místo včetně záhlaví,
   okolních řádků, poznámek na okraji a případného pokračování na další straně.
2. U odkazu zjistit dostupné připojené nástroje. Pokud umožní potřebnou akci,
   použít je; pro interaktivní prohlížeč dodržet jeho aktuální instrukce.
   Nevymýšlet názvy nástrojů a nepředpokládat přítomnost Playwrightu.
3. Pro Opavu přečíst [postup a omezení](references/opava.md), pro MZA
   [samostatný postup](references/mza.md). Živý režim vyžaduje soukromě evidované
   výslovné potvrzení souhlasu MZA pro IIIF; jinak použít místní import.
4. Před čtením ověřit na stránce archiv, fond/sbírku, signaturu, obec/farnost,
   rozsah let, druh knihy, stranu a číslo snímku. Rozlišovat rok knihy a rok události.
5. Zapsat citaci a přesný skutečně zjištěný odkaz. Chybějící údaj označit jako chybějící.
   Citaci ani adresu snímku nevymýšlet. Právní dostupnost mladších údajů případně
   ověřit v aktuálních oficiálních podkladech, neodvozovat ji jen ze stáří svazku.
6. Pokud zdroj nelze otevřít, uložit událost `blocked` a důvod. Můžeš dále
   číst dodaný snímek, ale neoznačovat výsledek za ověřený v archivním prohlížeči.

## Získat nebo importovat jeden snímek MZA

1. Na požadavek „Stáhni snímek 167 z matriky Blansko č. 56 v nejvyšším
   dostupném rozlišení“ přečíst [referenci MZA](references/mza.md). Nevymýšlet
   URL ani zaměňovat interní ID detailu za číslo knihy. Pokud uživatel výslovně
   potvrdí souhlas MZA pro IIIF, uložit jeho potvrzení jako `user_attestation`
   do soukromého nastavení podle reference; nevydávat je za nezávisle ověřený
   dokument ani obecné povolení archivu. Použít `archive mza download --url
   <přesná-URL-s-image>` se soukromým `--workspace`. Bez souhlasu nabídnout
   uložení v prohlížeči nebo oficiální kopii. Samotný příznak není oprávnění.
   Při ochraně, blokaci nebo nepodložené obrazové adrese skončit bez další
   síťové cesty. Potvrdit úspěch až po skutečném výsledku s ověřenými rozměry.
2. Na „Importuj tuto kvalitní kopii matriky do našeho badatelského projektu“
   použít `scripts/family_tree.py --workspace <soukromá-složka> archive mza import
   <soubor> --url <skutečná-URL>`. Doplnit skutečně známou identifikaci
   `--reference`, `--image-number`, způsob získání `--method` a případně čas
   `--acquired-at`. Bez podkladu nepoužívat `--digital-copy original`.
3. Na „Ověř, jestli máme tento snímek už uložený, a zobraz jeho rozlišení“
   použít `archive mza inspect --url <URL>` se soukromým `--workspace`.
   Volitelné `--file <soubor>` porovná i SHA-256. Kontrola je místní a bez sítě;
   nezjišťuje dostupné rozlišení na serveru. Stav oprávnění neznamená
   úspěšně ověřené spojení.
4. Import zachová bajty ve `sources/`, založí `unread` záznam a uloží metadata
   přímo do badatelského stavu. Nevytváří podpořená tvrzení ani vizuální ověření.
   Opakování stejného importu nemění přepis ani revizi. Stejná URL s jinými
   bajty je jiná kopie, stejný SHA-256 s jinou URL zachová oba původy.
5. Při následném `record put` zachovat `source.acquisition`, soubor i SHA-256;
   při věcném doplnění identifikace udržet `source.reference` a metadata shodná.
   Aktuální revizi vždy znovu načíst. Export a obnova přenášejí snímek i metadata.
6. Lokální Codex může spouštět CLI s Pythonem a Pillow. V ChatGPT bez přístupu
   k souborům nebo potřebnému prostředí neslibovat spuštění ani živý přístup;
   provést dostupnou část a uvést konkrétní chybějící možnost.

## Připravit snímek a přečíst zápis

1. Zachovat původní soubor beze změny ve `sources/` soukromé pracovní složky.
2. Pro obyčejný výřez použít
   `scripts/family_tree.py image crop <originál> <výstup.png> --box x0,y0,x1,y1`.
   Souřadnice jsou zlomky 0–1 po EXIF orientaci. Výřez zahrnout velkoryse.
   Potřeba je Pillow; podrobnosti jsou v [referenci dat](references/data.md).
3. Vizuálně prohlédnout originál i výřez skutečným nástrojem pro obrázky.
   Skript pouze ořezává; nečte písmo a nepotvrzuje správnost přepisu.
   Pro široký zápis lze použít `scripts/family_tree.py image split`, pro kontrolu
   rozsahu `scripts/family_tree.py image mark` a pro přehled několika již uložených
   snímků `scripts/family_tree.py image sheet`. Tyto
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

## Spravovat obecný model

Při práci s více osobami, příbuzenskými vazbami, alternativními údaji nebo
rozpory číst [referenci modelu](references/model.md).

- Pracovní osoba je pouze kontejner identity. Jméno, datum, místo i vazbu ukládat
  jako samostatná tvrzení, pokud mají být dokazována.
- Vztah uvádí účastníky a role; jeho pravdivost vyjadřuje tvrzení se subjektem
  `relationship`, nikoli samotná existence vztahu.
- Tvrzení `supported` či `rejected` musí mít citaci a zdůvodnění. Převzaté údaje
  z GEDCOM nebo rodinného podání ponechat `unverified`.
- Rozporná tvrzení nemazat ani automaticky neslučovat. Spojit je otevřeným
  konfliktem a při řešení uchovat odůvodnění i všechny původní varianty.
- Model měnit atomicky příkazem `family_tree.py ... model apply`; před změnou
  vždy načíst aktuální revizi. Formát 1 migrovat pouze výslovným `project migrate`.

## Uložit výsledek a umožnit navázání

1. Připravit záznam podle `assets/record.json`; číst [datovou referenci](references/data.md).
   V soukromé složce vyplnit přepis, překlad, interpretaci, nejistoty a citaci.
2. Načíst poslední `revision` pomocí `resume`. Pro změnu použít:
   `python3 scripts/family_tree.py --workspace <složka> record put <záznam.json> --expected-revision <n> --next-step "Konkrétní další krok"`.
   Změna obsahuje celý jeden záznam; ostatní záznamy zůstanou zachované a předchozí stav se zálohuje.
3. Negativní hledání nebo blokaci uložit příkazem `project log` s `--result not_found|blocked|note`,
   `--scope "Kniha, roky, snímky a dotaz"`, `--expected-revision <n>` a `--next-step`.
4. Spustit `check`. Kontrola ověřuje strukturu, citace pro `reviewed`, SHA-256 snímků
   a explicitní důvody ztotožnění. Nepotvrzuje paleografickou či historickou správnost.
   Potom spustit `audit`; ten nemění stav a vypíše neblokující varování, například
   chybějící překlad či interpretaci, otevřené nejistoty nebo stejnou citaci u
   více záznamů. Varování posoudit věcně, neodstraňovat je mechanicky.
5. Při změně revize načíst stav znovu a věcně spojit změny. Při změně kontrolního součtu
   nejprve vyšetřit rozdíl, neoznačit nový soubor automaticky za původní.
6. Před přenosem spustit `check` a vytvořit balíček příkazem
   `family_tree.py --workspace <složka> project export <výstup.zip>`. Výstup musí být mimo
   badatelskou složku i git repozitář. Uchovat vrácený SHA-256; podrobnosti jsou
   v [datové referenci](references/data.md).
7. Balíček uložit do uživatelem určeného trvalého soukromého úložiště. Lokální
   skript jej nenahrává ani nešifruje; přístupová práva a přenos řeší zvolené úložiště.
8. Při navázání obnovit balíček příkazem `project restore` do nové neexistující
   složky, znovu spustit `project check` a `project resume` a porovnat revizi,
   další krok a kontrolní součty.
9. Potvrdit trvalé uložení až po úspěšném zápisu a zpětném ověření. Jinak říci,
   že stav zůstává pouze v pracovní kopii. Neslibovat navázání závislé na
   neuložených souborech.
10. Stručně shrnout zjištění, nejistoty, zdroj a další krok. Zobrazit relevantní výřez,
    pokud je dostupný a prostředí to podporuje. Nezveřejňovat soukromá data v repozitáři.

## Publikovat podporovaná tvrzení do Gramps Web

Při výslovném požadavku na Gramps přečíst [referenci Gramps](references/gramps.md).

1. `research.json` zůstává autoritativním badatelským stavem; Gramps Web je
   odvozená soukromá vrstva.
2. Nejprve spustit `gramps probe`. Heslo nedávat do argumentu, plánu ani logu.
3. Vytvořit soukromý plán mimo Git příkazem `gramps plan` a zkontrolovat
   varování, vyloučená tvrzení a počty `create`, `unchanged`, `conflict`.
4. Přenášet jen `supported` tvrzení mimo otevřené konflikty. Pracovní popisek
   osoby nepovažovat za doložené jméno.
5. `gramps push` použít jen na zkontrolovaný plán a testovací či zálohovaný
   strom. Adaptér nic nemaže ani nepřepisuje; kolizi řešit ručně.
6. Po síťové chybě či úspěšném zápisu spustit `gramps status`. Zápis neopakovat
   naslepo, protože vzdálené vytvoření objektů nelze lokálně vrátit.
7. Soubory pramenů, neověřená tvrzení, zamítnuté varianty a úplná struktura
   konfliktů zůstávají v soukromém badatelském stavu.

Při výslovném požadavku publikovat badatelské úkoly používat oddělený tok
`gramps tasks probe/plan/push`. Vstupní JSON i plán uchovat mimo Git. Úkol není
genealogické tvrzení: v Gramps Web vzniká jako soukromý `Source` s tagem
`ToDo`, atributy `Status` a `Priority` a volitelnou poznámkou `To Do`.
Před zápisem zkontrolovat plán a kolize. Stabilní ID brání duplicitám; existující
stav, prioritu, titul ani text úkolu adaptér nepřepisuje. Automatické odvození
úkolů z badatelského stavu není součástí tohoto toku, vstup musí obsahovat
explicitně zkontrolovaný seznam.

## Respektovat archiv a rozsah

- Na jednom archivu pracovat postupně a bez souběžného listování. Použít uložené snímky.
- Při blokaci nebo CAPTCHA nepřidávat alternativní síťové cesty. Řídit se pokyny nástroje;
  pokud je nutná akce uživatele, předat pouze potřebný krok.
- Bez dostupného pramene nehlásit dohledání. Odhad a hypotézu vždy označit.
- Obousměrná synchronizace Gramps, hromadné hledání, vizualizace grafu a rodinný
  web jsou mimo tuto verzi. U takového požadavku pojmenovat chybějící funkci a
  udělat dostupnou část práce.

Původ adaptace a úplná licence: [references/upstream.md](references/upstream.md), `LICENSE`.
