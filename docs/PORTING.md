# Převod původního projektu

Zdroj: https://github.com/sarsonj/rodokmen-skill/tree/0fb0c0379abf51a9af92d363992799fcd38eb23a

Datum inventury: 10. listopadu 2026. Funkční audit pro verzi 0.2.0 dokončen
12. listopadu 2026. Referenční revize byla při auditu zároveň aktuálním `origin/HEAD`
původního projektu. Níže je úplný katalog 31 souborů v
`skills/rodokmen/tools`. U všech byl zkontrolován účel, vstupy, hlavní
závislosti a vazba na původní datový model; detailní převzetí a testy proběhly
jen u vybraných offline funkcí. Nejde o bezpečnostní audit všech síťových
protokolů ani potvrzení aktuálního přístupu ke všem portálům.

## Vybrané minimum

- `skills/family-tree-chatgpt/SKILL.md`: přepracovaný postup pro jeden zápis, výběr skutečně dostupných nástrojů a přiznaná omezení.
- `crop.py`: normalizované souřadnice dle původního `vyrez.py`, Python 3.11+ a Pillow 13.0.0 místo ImageMagicku, PNG bez EXIF, kontrolní součty a ochrana před přepsáním.
- `research.py`: nový lokální zápisník ve standardní knihovně Pythonu 3.11+, oddělené čtení/totožnost, historie, revize, součty a deník.
- `family_tree.py`: nové jednotné CLI nad místními projektovými, modelovými,
  GEDCOM a obrazovými funkcemi; nejde o převzatý upstreamový skript.
- `gedcom.py`: nový bezpečný offline import podle veřejné specifikace GEDCOM;
  původní parser ani datové schéma se nekopírují, ale bezpečně je adaptovaná
  užitečná fronta předků a Kekulého číslování.
- `image_review.py`: Pillow adaptace pracovních postupů `overit.py`,
  `ramecek.py` a lokální části `mapa_knihy.py`; žádný síťový režim.
- `research.py audit`: přebírá rozlišení blokujících chyb a neblokujících
  výzkumných varování z `kontrola.py`, ale kontroly jsou přepsané pro zdejší
  JSON schéma.
- `references/methodology.md`: zkrácená adaptace nadčasových pravidel z
  `reference/metodika.md` a `matriky.md`.

Síťové stahovače, původní `osoby.py`, Astro web, Claude manifesty/hooky a
modelové instrukce nejsou součástí této verze.

## Výsledek funkčního auditu

### Adaptováno nyní

- Výřez, rozdělení širokého zápisu, kontrastní pracovní kopie, označení
  kontrolované oblasti a lokální přehled více snímků.
- Bezpečný GEDCOM import, výzkumný plán a volitelná fronta vývodu předků.
- Strukturální `check` a samostatný čtecí `audit` kvality badatelského stavu.
- Metodika rozlišení pramene, tvrzení, interpretace a totožnosti.

### Odloženo do odpovídajícího datového modelu

- `fan_chart.py`, `napady.py`, `mista.py` a část `kontrola.py` potřebují obecný
  model osob, vztahů, událostí a míst. Převzetí před tímto modelem by zakonzervovalo
  upstreamový Pythonový formát `osoby.py`.
- `ftb_export.py` potřebuje skutečný neosobní vzorek podporované databáze a
  samostatný importní model; bez něj nelze ověřit ztrátu nebo záměnu údajů.
- `export_web.py` a šablona Astro jsou samostatná publikační fáze s kontrolou
  soukromí, nikoli základ badatelského nástroje.

### Záměrně nepřevzato nyní

- Archivní downloadery a vyhledávače používají konkrétní síťová rozhraní,
  externí programy nebo portálové postupy. Některé portály dnes vyžadují ruční
  browserový průchod či CAPTCHA. Převzetí bez živého ověření by mohlo porušit
  limity portálu nebo vytvořit nepravdivý dojem podpory.
- `slusne.py` je hodnotná brzda pro upstreamové síťové skripty, ale zdejší
  verze žádný přímý downloader nemá a interaktivní browser přes tento Python
  obal neprochází. Bude znovu posouzen s prvním schváleným síťovým adaptérem.
- Claude hook `hlidac_site.py`, aktualizátor `verze.py` a Claude části
  `novy_projekt.py` nejsou přenositelné do Codexu jako bezpečnostní hranice.

## Přehled nástrojů

| Původní nástroj | SHA-256 obsahu ve zdrojové revizi | Rozhodnutí |
|---|---|---|
| `ahmp_parse.py` | `e85aadfad3d364cfd1e6c18eaeb49b18946590a800b031d7d2434009a08d57c2` | Archivní/síťový nástroj: odložen, v této verzi nepřevzat a neotestován. |
| `ahmp_scan.py` | `d21a8254de2c4ee8214a4dba650a3278236bb823c9734474e1168b1037be1e63` | Archivní/síťový nástroj: odložen, v této verzi nepřevzat a neotestován. |
| `ahmp_search.sh` | `d5942afaaae56bc123ce45c925aa639c6ba344ffff763b214d2ebd152916333f` | Archivní/síťový nástroj: odložen, v této verzi nepřevzat a neotestován. |
| `anno.py` | `b8f66246caa20ef29e5b6c65996c2b0f3de6fcc332a7b7486f8a74293c50c099` | Archivní/síťový nástroj: odložen, v této verzi nepřevzat a neotestován. |
| `anno_snap.py` | `6e00180d742403844389db5754dd2d96ac00963329a24b5ad3918df856a55ec9` | Archivní/síťový nástroj: odložen, v této verzi nepřevzat a neotestován. |
| `aron_img.py` | `ae3bf1e3e345ac6483cbf18b6e636285d56099020d564d706a3d06d1cc15ebc9` | Archivní/síťový nástroj: odložen, v této verzi nepřevzat a neotestován. |
| `aron_search.py` | `8f31507d73b415142a54398f8fafb5f08c20bb69012c0cbeb17964f3cc07df2a` | Archivní/síťový nástroj: odložen, v této verzi nepřevzat a neotestován. |
| `cache.py` | `130cbae9ae83a90575c4171e23cb81a47d28b68ad974440c1f2c1120134cd4a7` | Posouzen; je mezipamětí upstreamových downloaderů. Zdejší offline deriváty pracují s lokálním originálem a síťovou cache nepotřebují. |
| `ebadatelna.py` | `399f9a5e4c86beb3098694cfd1b6469e326dd3e784c7131c562a7904d604dd09` | Archivní/síťový nástroj: odložen, v této verzi nepřevzat a neotestován. |
| `export_web.py` | `49a54f0bb3d0dc5b1ecb41009aadfde3046dcf5bad90cac651a5402a78f4ce4e` | Pozdější fáze: web, neimportováno. |
| `fan_chart.py` | `8a1ea238e43ec94bb814fc581d10b55810b68f38059ce393dc3025fb845f4569` | Pozdější fáze: vějíř, neimportováno. |
| `ftb_export.py` | `a2c14d6ba5784abff39e96af95feb8101af0c65747b313d4ca49bb177456118b` | Další fáze: MyHeritage, dosud nepřevzat ani neotestován. |
| `ged_import.py` | `c72c68f8331b2d36ed677c30af0311762642166ffa0c3facf5d8d014ffd233b9` | Parser a schéma nepřevzaty. Nový `scripts/gedcom.py` má oddělená tvrzení a podle užitečné upstreamové myšlenky nově volitelnou frontu předků, Kekulého pozice, detekci cyklu a bezpečné zastavení při více `FAMC`. |
| `hlidac_site.py` | `5572e5ff9937aecb07bc11b6278ae4839e021cdbfae799ad4c29567a3a587638` | Claude hook se nepřebírá; nelze jej považovat za ochranu ChatGPT. |
| `kontrola.py` | `db14294bd0d28981e34fd7234e742e0de92c1f649e6eb391cc7b16b6ad68c56e` | Datově specifické kontroly nepřevzaty. Princip chyb versus varování adaptován do `research.py audit`: stav čtení/totožnosti, chybějící vrstvy, otevřené nejistoty a možné duplicitní citace. |
| `kramerius.py` | `563ac9f62eda05241dc3fec6852e747064673873bd22b401c1c14c909b5481bd` | Archivní/síťový nástroj: odložen, v této verzi nepřevzat a neotestován. |
| `mapa_knihy.py` | `1d9cda51f371c7cab271360a26671a193df1d5b153c65a0a7a6acf485c5a7fd3` | Lokální montáž již uložených snímků adaptována jako `image_review.py sheet` s Pillow a limitem 60 souborů. Síťové režimy archivů nepřevzaty. |
| `matricula_batch.sh` | `ddd7b26127b0875b6696395b0e72bc1f53688c7abe4560ce2e593967bcc63753` | Archivní/síťový nástroj: odložen, v této verzi nepřevzat a neotestován. |
| `matricula_dl.sh` | `3161970ade8ff51a3256ebb61a0be9ea041a7361d7931aa99fe39ed522acd923` | Archivní/síťový nástroj: odložen, v této verzi nepřevzat a neotestován. |
| `mista.py` | `4fd7bd48e54ea26cb3ca539628e0bc3a49b0c7174739e1acda7bdffa60c53396` | Odloženo: geokódování a mapa. |
| `napady.py` | `6388959071cac74074e6b3b831c0687ece6bfa01f2c1e210e994d7c65d41133a` | Odloženo: příběhy a analýza většího stromu. |
| `novy_projekt.py` | `a559e4f8fa3510cc7d12a36b2e5d6a59a1ecff4c264f657fc9ae8738f99ab2d7` | Odložen; původní projekt/web/Claude nastavení, zde soukromá složka research.py. |
| `overit.py` | `b2af8b78522a17e3d9a79dbc2747dae1d2497df94304e445874376bc1e649a2c` | Pracovní postup adaptován jako `image_review.py split`: dvě překrývající se PNG, volitelný kontrast, součty, žádné přepsání a žádný ImageMagick. |
| `policie_prihlasky.py` | `b406a09b3a6b25fde59fb29fca1e91b669187f170e89096d350d748bb39818ce` | Archivní/síťový nástroj: odložen, v této verzi nepřevzat a neotestován. |
| `portafontium.py` | `6bac90c061b817878f6d7f66e78e78ad5e90afd63212518e421c8e9237a46894` | Archivní/síťový nástroj: odložen, v této verzi nepřevzat a neotestován. |
| `ramecek.py` | `c1cd7d0f6f57758f447f72872a2f096baf33ec892177bb619a3b29e2e98bb67a` | Pracovní postup adaptován jako `image_review.py mark`: více normalizovaných rámečků v nové soukromé PNG, bez změny originálu a bez původního `zvyrazneni.json`. |
| `slusne.py` | `c1037d12c54a95d4f850e8491089ab7cc72b991b20a7061cff8c4d949cacea9b` | Detailně posouzen. Hodnotná brzda, cache a stopky jsou svázané s upstreamovými downloadery a neřídí interaktivní browser. Převzít až s prvním povoleným síťovým adaptérem, jinak by vytvářela falešný pocit ochrany. |
| `soal_zoomify.py` | `a681999e46bc0c03268604e1d6ad30a2d5e6486bf032e7b526859ad66211bfa3` | Odložen do ověření živého přístupu a pravidel portálu. |
| `verze.py` | `ad5344408d36e2b40a1ecdd11c89468e02ca5665ad6c24ecd369f9009f10917d` | Původní aktualizátor se nepřebírá; zdroj je připnutý ke konkrétní revizi. |
| `vyrez.py` | `69ae2f48dccd1c2e527b00eaaf5714fa0782c71c08c3f1b3f6b342289fcfd985` | Princip adaptován do crop.py; Pillow, explicitní výstup, součty. |
| `zapis.py` | `c4ba202b6dd63720334539aa903096cce36e4ab69e4799dd043feffb605c0a72` | Odložen; původní datové schéma se nepřebírá, research.py je nová implementace. |

## Reference a šablony

- `SKILL.md`: adaptovaný hlavní postup.
- `reference/portaly.md`, Opava: zúžený postup, živý přístup neověřen.
- `reference/data.md`: původní formát nepřebírán; zde vlastní JSON schéma verze 1.
- `reference/metodika.md`, `matriky.md`: nadčasová pravidla práce s důkazy,
  ztotožnění, hledání v knihách a mrtvých bodů jsou zkráceně adaptovaná v
  `references/methodology.md`; proměnlivé právní lhůty a technické pokyny pro
  Claude/ImageMagick se nepřebírají.
- `reference/pribehy.md`, `soukromi.md`, `web.md`, `instalace.md`: příběhy a
  web patří do pozdější publikační fáze; základní pravidla soukromí jsou už v
  hlavním skillu a metodice, instalační kroky Claude se nepřebírají.
- `template/`: nepřevzato; vlastní minimální šablona jednoho záznamu.

## Přenos mezi konverzacemi

Lokálně funguje uložení a obnovení v oddělených procesech i export úplného
stavu do ZIP s manifestem, velikostmi a SHA-256. Obnova odmítá změněný obsah,
nebezpečné cesty, symlinky a existující cíl a po rozbalení znovu kontroluje
badatelský stav. Skript neobsahuje cloudového klienta ani vlastní šifrování.
Přenos skutečného soukromého bádání přes trvalé úložiště do nové konverzace byl
ověřen 12. listopadu 2026: nová konverzace obnovila revizi 2, provedla další
zápis s optimistickým řízením souběhu, ověřila revizi 3 a vytvořila nový ZIP.
Skript nadále neobsahuje cloudového klienta; trvalost, přístupová práva a
případné šifrování zajišťuje uživatelem zvolené soukromé úložiště.

## Licence

Původní MIT oznámení je beze změny v kořenovém `LICENSE` i v balíčku. Mapování adaptovaných souborů je v `skills/family-tree-chatgpt/references/upstream.md`.
