# MZA Brno: práce pouze přes archivní prohlížeč

Stav: živý pilot v prohlížeči Codex 11. listopadu 2026 ověřil hledání podle
obce, detail konkrétní knihy, ruční průchod přes Altcha, zobrazení jednoho
skutečného snímku a výřez ze screenshotu. Podrobnosti jsou v
`../../../docs/VALIDATION.md`.

Výchozí portál: https://www.mza.cz/actapublica/. Aktuální podmínky jsou na
https://www.mza.cz/actapublica/page/view/podminky-uziti-sluzeb. Před dalším
použitím ověřit, že se adresa, rozhraní a podmínky nezměnily.

1. Ve viditelném rozhraní hledat podle obce, původce nebo čísla knihy.
2. V detailu porovnat číslo knihy, případné původní číslo a svazek, původce,
   druh církve, rozsahy narozených, oddaných a zemřelých a zahrnuté lokality.
3. Pokud se objeví Altcha nebo jiná ochrana, předat ji uživateli. Neobcházet ji
   jiným klientem, interním koncovým bodem ani automatizovaným řešením.
4. Snímky otevírat a měnit pouze ovládacími prvky prohlížeče MZA. Pro tento
   projekt nepoužívat síťové stahování, přístupové tokeny, adresy dlaždic ani
   skládání obrazových dat.
5. Pro jednotlivý zápis pořídit screenshot právě viditelné stránky a uchovat
   jej v soukromé pracovní složce. Označit jej jako screenshot prohlížeče,
   nikoli jako archivní originál nebo plné rozlišení.
6. Citovat číslo knihy, původce, obsah a rozsah let, číslo snímku a přesnou
   skutečně otevřenou adresu s identifikátorem obrázku. Adresu neodhadovat.
7. Výřez vytvářet ze zachovaného screenshotu pomocí
   `scripts/family_tree.py image crop` a
   vizuálně zkontrolovat screenshot i výřez. Kontrolní součty se vztahují k
   pracovnímu screenshotu, ne k původnímu souboru MZA.
8. Bez odemčeného prohlížeče nebo uživatelem dodaného snímku uložit blokaci a
   chybějící rozsah. Nepokoušet se ochranu obejít alternativní síťovou cestou.

Pilot musí uvést datum a prostředí, konkrétní knihu a snímek, ověřenou citaci,
přesný odkaz, druh zachovaného obrazového podkladu a omezení. Rodinné údaje a
snímky patří mimo veřejný repozitář.
