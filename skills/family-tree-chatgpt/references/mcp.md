# MCP-first: Family Tree 2.1 (produkční režim)

Tato reference platí, **pokud je v aktuální konverzaci skutečně připojen a dostupný Family Tree MCP server**. Přesný seznam a schémata nástrojů načítej z připojení, nikoli z paměti nebo příkladů. Neprovozuj vedle něj nezávislý `research.json` jako druhou autoritativní databázi.

## Zdroje pravdy a režimy

- **SQLite badatelská DB** přes Family Tree MCP: pracovní osoby, záznamy, zdroje, citace, tvrzení, přepisy, varianty, konflikty a audit. Toto je v připojeném režimu primární evidence.
- **Gramps Web**: vizuální *pracovní* rodokmen zahrnující doložené údaje, předběžná tvrzení i výslovně označené hypotézy. Není měřítkem jistoty údajů.
- **Offline CLI** `scripts/family_tree.py` a soukromý `research.json`: pouze pro výslovně offline projekt nebo při nedostupném MCP po dohodě s uživatelem. Neměň nebo nepřepisuj takto stav vzdálené SQLite bez řízeného importu.
- `rev13_a` a `rev13_b` jsou dvě různé historické importní větve; nikdy je implicitně nespojuj. Před každým zápisem musí být známý konkrétní `branch_key`.

## Běžný krátký postup

1. Zavolej `database_status`, podle potřeby `search_persons`/`search_records`, `get_record`, `get_claim`, `get_media_info` a `get_media`. Pro audit `list_audit_revisions` a `get_audit_revision`. Zobrazuj rozdíly mezi zdroji, neodstraňuj je bez důkazu.
2. Získaný zápis přepiš, přelož a interpretuj samostatně. Každý doložený údaj i alternativa dostane citaci nebo explicitní označení původu; nejistotu ponech viditelnou.
3. Na pokyn „ulož nález“ použij **jedno** `research_save_findings` s `branch_key`, stabilním `idempotency_key`, `source`, `record` a polem `claims`; volitelně `persons`, `transcription`, `translation`, `interpretation`, `uncertainties` a `locator`. Pokud nemáš výslovný pokyn k zápisu, ponech `preview_only=true`; při schváleném uložení `preview_only=false`. Není potřeba individuální SHA souhlas u každého tvrzení. Zopakování po nejistém výsledku nejprve ověř čtením, neprováděj naslepo nové ID.
4. Nová tvrzení začínají `unverified`; `reading_status=reviewed` **neznamená**, že ztotožnění osoby nebo výklad je doložený. Nikdy nevytvářej přesné datum, identitu ani vztah pouhou dedukcí.
5. Ověř výsledek zpětným načtením a uveď ID, větev, případný rozpor a stav zápisu. Při chybě nepředstírej uložení.

Poznámka ke schématu: při `claims[].subject_kind="record"` je aktuální záznam implicitní; nevkládej `subject_id`, pokud ho připojený nástroj nepřijímá. Konkrétní pole pro nové zdroje a osoby ber z aktuálního schématu MCP; nedoplňuj náhodná ID ani neověřené referenční údaje.

## Vizuální Gramps: ukládej i neověřené údaje

Uživatel chce vidět **i neověřené osoby, alternativní data a pracovní vazby**, aby mohl plánovat další pátrání. Nepoužívej strategii „do Gramps jen `supported`“. Všechny publikační kroky však musí zachovat rozdíl mezi tvrzením a doloženým faktem.

| Badatelské posouzení | Zobrazení ve Gramps |
|---|---|
| DOLOŽENO | Běžný údaj s citací a stavem „Doloženo“ |
| PRAVDĚPODOBNÉ | Předběžný údaj s označením „Pravděpodobné“, odůvodněním a citací/zdrojem |
| HYPOTÉZA | Zřetelná „Hypotéza“ a úkol, jak ji vyvrátit nebo potvrdit |
| NEVYŘEŠENO | „Nevyřešeno“ a otevřená otázka; žádné automatické definitivní pole |
| VYVRÁCENO | Nechat v SQLite historii, případně jako výzkumnou poznámku; neoznačovat za platný fakt |

SQL `claim.status` (`unverified/supported/rejected`) a `evidence_level` **nejsou** samy o sobě přímým ekvivalentem těchto pěti uživatelských úrovní. Konkrétní stupeň piš podle doloženého badatelského úsudku do poznámky/metadat, neodvozuj automaticky z technického pole.

### Bezpečnost při publikaci

1. Před zápisem zkontroluj `gramps_status`, cílový strom (`gramps_list_trees`) a přesné existující Gramps ID/handle (`gramps_find`, `gramps_get`). Nikdy neslučuj podle shody jména.
2. `gramps_publish_person` je **přímé vytvoření jedné osoby** (případně událostí a rodinných vazeb) s `preview_only`; samo o sobě nemá parametr pro úplnou klasifikaci jistoty ani volný výzkumný komentář. **Nepoužívej ho pro nejisté záznamy, pokud jejich stav nelze současně a spolehlivě ve Grampsu označit.**
3. Pro bohatší objekty existují `gramps_prepare_write` a `gramps_commit_write`, ale jejich přesné schéma, podporu vazeb na Note/Tag/Citation a požadavky na souhlas ověř dle živých definic. Nepředstírej existenci `research_publish_to_gramps`; v současném připojení není k dispozici.
4. U každého neověřeného údaje musí být v Grampsu dostupný zřetelný stav, podklad či identifikátor SQLite tvrzení, citace, datum a otázka pro další ověření. Je-li k dispozici Tag/Note/attribute, použij jej konzistentně. Pokud ne, nepřenášej nejistou hodnotu do pole vypadajícího jako definitivní; zachovej ji v SQLite, případně jako výzkumnou poznámku.
5. Alternativní čp. **30/36** nesmí skončit v jednom vybraném čísle domu bez rozhodnutí. Lze zachovat obě varianty v označené poznámce a odkazu na konfliktní podklady, nikoli jednu vydávat za definitivní.
6. U hypotetických rodičovských vazeb vyžaduj viditelné označení míry jistoty **na vztahu nebo bezprostředně připojené poznámce**; bez této možnosti nepřipojuj vazbu jako potvrzenou.
7. Vzniklý Gramps objekt vždy znovu načti podle ID/handle. Při časovém limitu nebo síťové chybě nepoužívej slepý retry a nezakládej duplicitu.
8. Potvrzení uživatele pro minulou synchronizaci („bez schvalování“) nebylo trvalým povolením budoucích zápisů. Nový zápis vyžaduje aktuální pokyn a oprávnění podle používaného konektoru.

Detailní rozdíl MCP vs. původní offline export uvádí [gramps.md](gramps.md). Offline `gramps plan/push` stále podporuje jen `supported` tvrzení; **jeho omezení nelze zaměňovat za metodické pravidlo projektu**.

## Co stávající API zatím neumí samo

- Neexistuje jediné `research_publish_to_gramps` podle ID tvrzení ze SQLite, které by automaticky přeneslo i jejich stav. Neuváděj export jako hotový bez explicitního API a reverzní kontroly.
- `research_save_findings` pouze zapisuje badatelský nález; automaticky nesynchronizuje Gramps.
- Neprováděj automatické slučování větví, mazaní, skryté opravy konfliktních hodnot ani hromadné publikování hypotéz.
