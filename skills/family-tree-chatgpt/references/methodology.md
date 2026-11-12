# Metodika genealogického ověřování

Tento postup je adaptovaný z `skills/rodokmen/reference/metodika.md` a
`matriky.md` projektu `sarsonj/rodokmen-skill`, revize
`0fb0c0379abf51a9af92d363992799fcd38eb23a`, MIT. Je přepracovaný pro zdejší
model záznamů a neobsahuje časově proměnlivé právní lhůty ani automatické
stahování archivů.

## Co je doklad a co je pouze vodítko

- Originální archivní snímek s přesnou citací je základ. Rejstřík, opis nebo
  druhopis mohou pomoci, ale nejsou automaticky nezávislým potvrzením originálu.
- GEDCOM, cizí rodokmen, rodinné vyprávění a vyhledávací index jsou tvrzení k
  ověření. Přítomnost odkazu `SOUR` v GEDCOMu neznamená, že byl pramen otevřený
  a vizuálně zkontrolovaný.
- Přepis zachycuje, co je na snímku. Překlad převádí význam. Interpretace
  vysvětluje důsledky. Závěr o totožnosti porovnává více podkladů. Tyto vrstvy
  neslučuj.
- Negativní hledání je výsledek jen tehdy, když je uvedený pramen, rozsah let či
  snímků, hledané varianty a způsob kontroly.

## Výzkumný cyklus

1. Polož jednu konkrétní otázku, například „Kteří rodiče jsou uvedeni u této
   nevěsty?“ nebo „Patří tyto dva zápisy stejné osobě?“
2. Sepiš známá tvrzení a jejich původ. Neověřený strom drž odděleně od
   archivních záznamů.
3. Vyjmenuj možné kandidáty a údaj, který je může rozlišit: rodiče, partner,
   dům, povolání, obec, věk nebo svědci.
4. Začni u nejmladší známé události s místem, pokud může odkazovat na rodiče či
   původ. Je to strategie hledání, nikoli důkaz správnosti stromu.
5. Otevři konkrétní pramen, ověř kontext knihy a ulož citaci, snímek a výřez.
6. Přepiš celý relevantní zápis včetně záhlaví a okrajových poznámek. Nejistoty
   ponech explicitní.
7. Zapiš, co záznam podporuje, co vyvrací a co stále neřeší. Aktualizuj další
   krok tak, aby byl proveditelný bez paměti konverzace.

## Ztotožnění osob

- Stejné jméno a přibližný rok nestačí. Pro `supported` hledej nejméně dva
  rozlišující znaky, ideálně z různých zápisů: oba rodiče, partner, přesné datum,
  číslo domu, obec, povolání nebo stabilní okruh svědků a kmotrů.
- Dva údaje opsané z jednoho staršího záznamu nejsou dva nezávislé doklady.
  Posuzuj, kdo údaj oznámil a jak dlouho po události vznikl.
- Před sloučením vypiš ostatní stejnojmenné kandidáty ve stejné oblasti a proč
  nesedí. Uveď také, jaký budoucí nález by závěr vyvrátil.
- Číslo domu je silná stopa, ale ověř přečíslování a možnost více domácností v
  jednom domě. Kmotři a svědci ukazují sociální okruh, ne automaticky příbuzenství.
- Výměnkář nemusí být otec nového hospodáře; může jít o tchána, nevlastního
  rodiče nebo nepříbuzného předchozího držitele.
- Rodné a provdané příjmení, jméno po chalupě, jazyková varianta a změna
  pravopisu mohou označovat jednu osobu. Shodu přesto dolož dalšími znaky.
- Rozpor nemaž. Zapiš obě podoby, jejich prameny a důvod, proč má některá
  informace větší váhu.

## Jak hledat v matrice

- Ověř farnost pro obec a období; hranice se měnily. Potom vyber správný druh
  knihy a rok.
- Index je navigace, ne náhrada zápisu. Odkaz na folio ověř na skutečné stránce
  a při neúspěchu prohlédni sousední stránky.
- Kniha může být řazená po obcích, nikoli čistě chronologicky. Než uzavřeš
  „nenalezeno“, zjisti rozvržení oddílů a zda hledaná obec do knihy patří.
- Sňatek hledej v oddílu či farnosti, kde se podle zápisu konal; často, nikoli
  vždy, jde o bydliště nevěsty. Křest dítěte může obsahovat pozdější poznámku o
  sňatku rodičů.
- U věku dopočteného z úmrtí nebo sňatku použij širší časové okno. Přesný rok z
  pozdního pramene může být nepřesný.
- Pokud rodina chybí, ověř jiné vyznání, civilní řadu, vojenskou matriku,
  druhopis nebo samostatnou knihu konkrétní obce. Dostupnost a přístupová
  pravidla ověřuj v aktuálních oficiálních zdrojích.

## Kontrola čtení a obrazových derivátů

- Originál nikdy nepřepisuj. Výřez, kontrastní kopie, rozdělené poloviny a
  označený náhled jsou pouze pracovní deriváty.
- U vybledlého snímku lze vytvořit kontrastní pracovní kopii, ale přepis
  porovnej i s originálem a úpravu zaznamenej.
- Široký zápis rozděl na dvě překrývající se části, aby se neztratil text v
  místě dělení. Rámečkem označ, kterou oblast přepis skutečně pokrývá.
- Nejasné písmeno porovnávej se stejnou rukou na téže stránce. Očekávané jméno
  z rodokmenu nesmí rozhodnout čtení.

## Mrtvý bod

Když se větev zastaví, změň druh pramene, nikoli úroveň jistoty:

- gruntovní, pozemkové a sirotčí knihy mohou spojit dům, držitele a dědice;
- svatební smlouvy a pozůstalosti mohou uvést původ a příbuzné mimo farnost;
- sčítání, pobytové přihlášky, domovské listy a vojenské prameny mohou odhalit
  migraci;
- rejstřík, druhopis nebo jiná církevní řada mohou nahradit chybějící matriku;
- u nemanželského dítěte hledej pozdější legitimační poznámku, sňatek matky a
  soudní či poručenské záznamy.

Každou neúspěšnou větev zapiš s rozsahem. Další badatel pak nebude opakovat
stejnou slepou cestu ani z neúspěchu vytvářet neexistující fakt.

## Soukromí

- Rodinné GEDCOMy, snímky, přepisy a badatelské deníky patří mimo Git.
- U žijících a nedávno zemřelých nezveřejňuj adresy, kontakty, zdravotní údaje,
  rodná čísla ani citlivé rodinné okolnosti bez výslovného souhlasu.
- Přihlášení, platby a souhlasy na cizích službách provádí uživatel. Nástroj
  nemá provádět hromadné procházení účtů ani obcházet ochranné výzvy.
