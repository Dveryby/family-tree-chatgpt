# Pravidla pro práci na projektu

## Cíl a stav
- Před změnami přečti README.md a zkontroluj aktuální stav repozitáře.
- Cílem projektu je obecný nástroj pro dohledatelný genealogický výzkum; osoby
  z pilotních zápisů jsou testovací případy, ne výzkumný cíl projektu.
- První milník je jeden doložený průchod od matričního zápisu po uložený
  výsledek a navázání v nové konverzaci; tento akceptační milník je splněný.
- Za hotové označuj pouze kroky s důkazem; plán, implementace a ověření jsou odlišné stavy.
- Komunikuj s uživatelem česky. Technické volby řeš samostatně v rámci zadání.

## Genealogická přesnost
- Nikdy nevymýšlej osoby, data, citace ani nečitelný obsah zápisu.
- Přepis originálu, překlad, interpretaci a ztotožnění osoby veď odděleně.
- Nejisté čtení označ (?), nečitelné místo […]; u hypotézy uveď podklady a otevřené rozpory.
- Čitelný zápis nedokazuje sám o sobě totožnost osoby nebo příbuzenskou vazbu.
- Každý badatelský závěr musí jít dohledat k prameni; eviduj i negativní hledání a jeho rozsah.

## Soukromí a archivy
- Repozitář obsahuje obecný kód, návody a syntetická testovací data.
- Rodinné soubory GEDCOM, originální dokumenty, snímky, skutečné přepisy a badatelské deníky ukládej odděleně do soukromého úložiště.
- Před každým commitem kontroluj celý obsah změn; .gitignore není úplná ochrana.
- Přístupové údaje nesmí být v kódu, logu ani commitu.
- Respektuj podmínky a limity archivů. Při blokaci zastav požadavky a blokaci neobcházej.
- Původní snímek zachovej; pracovní výřez nebo zvýšení kontrastu nesmí změnit obsah písma.

## Převod původního projektu
- Před převzetím souboru z sarsonj/rodokmen-skill přečti jeho obsah a ověř závislosti.
- Zaznamenej zdrojovou revizi, cestu souboru a místní úpravy.
- S převzatým kódem nebo podstatnými částmi dokumentace zachovej úplné původní licenční a autorské oznámení MIT.
- Pravidla, cesty, hooky a nástroje specifické pro Claude přizpůsob cílovému prostředí; nepovažuj je za přenositelné bez ověření.
- Přístup k jednotlivým archivům a dostupnost nástrojů ověř prakticky, neslibuj je pouze na základě dokumentace.

## Vývoj a ověření
- Dělej malé, kontrolovatelné změny.
- Používej syntetická data pro automatické testy.
- U změn parsování, vazeb osob a ukládání dat testuj skutečné okrajové případy a ztrátu či záměnu údajů.
- U čistě dokumentačních změn stačí kontrola obsahu a odkazů.
