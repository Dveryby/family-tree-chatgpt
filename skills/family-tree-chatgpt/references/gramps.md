# Propojení s Gramps Web

První adaptér je záměrně jednosměrný a `append-only`. Převádí podporovaná
tvrzení z platného `research.json` formátu 2 do soukromých objektů Gramps Web.
Nevytváří fakta z pracovních popisků, nic na serveru nemaže a existující
neshodný objekt nepřepisuje.

## Požadavky a přihlášení

- Gramps Web API 3.x a HTTPS; HTTP lze povolit jen výslovným `--allow-http`
  pro izolovaný lokální test.
- Účet s právem zapisovat objekty, obvykle samostatný `Editor` v testovacím
  stromu.
- Heslo se nikdy nepředává jako argument. Při interaktivním použití ho příkaz
  bezpečně vyžádá; pro neinteraktivní běh lze použít proměnnou
  `GRAMPS_WEB_PASSWORD`.
- Alternativou je krátkodobý holý access token v `GRAMPS_WEB_TOKEN`. Token ani
  heslo se neukládají do plánu, badatelského stavu nebo výstupu příkazu.

Nejprve pouze ověř spojení:

```sh
python3 scripts/family_tree.py gramps probe \
  --url https://rodokmen.example.cz \
  --username editor
```

`probe` nezapisuje. Vrací verzi API a Gramps, ID a název aktivního stromu,
počty objektů a informaci o kompatibilitě. URL může končit kořenem instance
nebo `/api`.

## Plán, zápis a kontrola

Plán obsahuje soukromé genealogické údaje, proto musí ležet mimo Git stejně
jako `research.json`. Nový soubor dostane oprávnění `0600`.

```sh
python3 scripts/family_tree.py --workspace /soukroma/badani \
  gramps plan /soukroma/gramps-plan.json \
  --url https://rodokmen.example.cz --username editor

python3 scripts/family_tree.py --workspace /soukroma/badani \
  gramps push /soukroma/gramps-plan.json \
  --url https://rodokmen.example.cz --username editor

python3 scripts/family_tree.py --workspace /soukroma/badani \
  gramps status \
  --url https://rodokmen.example.cz --username editor
```

`plan` nejprve spustí strukturální kontrolu badatelského stavu a načte každý
zamýšlený objekt ze serveru. Operace jsou:

| Stav | Význam |
|---|---|
| `create` | Stabilní handle na serveru neexistuje; objekt lze vytvořit |
| `unchanged` | Objekt už obsahuje všechna pole vytvořená adaptérem |
| `conflict` | Stejný stabilní handle existuje s jiným obsahem; nic se nepřepíše |

`push` přijímá pouze nezměněný plán pro stejný server, strom, revizi a přesný
SHA-256 aktuálního `research.json`. Bezprostředně před zápisem znovu ověří, že
nové objekty stále neexistují. Všechny `create` objekty odešle jednou dávkou a
potom každý výsledek načte zpět. Kolize nebo změna stavu celý příkaz zastaví.
Protože vzdálené vytvoření nelze lokálně vrátit, při síťové chybě vždy spusť
`status` a nevytvářej naslepo nový plán.

`status` nic neukládá. Výsledek `pending` znamená nové objekty k vytvoření,
`synchronized` shodu spravovaných polí a `conflict` kolizi vyžadující ruční
posouzení.

## Badatelské úkoly v Gramps Web

Úkoly používají samostatný tok a nevstupují do exportu podporovaných tvrzení.
Gramps Web reprezentuje úkol jako soukromý `Source` s tagem `ToDo`, atributy
`Status` a `Priority` a volitelnou připojenou `Note` typu `To Do`.

Nejprve bez zápisu ověř API a tag `ToDo`:

```sh
python3 scripts/family_tree.py gramps tasks probe \
  --url https://rodokmen.example.cz --username editor
```

Vstupní soubor mimo Git má tento formát:

```json
{
  "schema_version": 1,
  "tasks": [
    {
      "id": "missing-marriage:person-P004",
      "title": "Dohledat sňatek Jana Nováka",
      "description": "Prohledat matriku oddaných 1800–1812.",
      "priority": "high"
    }
  ]
}
```

`id` je stabilní technický identifikátor dlouhý nejvýše 128 znaků bez mezer.
Priorita je `high`, `medium` nebo `low`; výchozí hodnota je `medium`. Nový úkol
vždy vzniká se stavem `Open` a jako soukromý. JSON může obsahovat nejvýše 500
úkolů a nesmí obsahovat jiná pole.

```sh
python3 scripts/family_tree.py gramps tasks plan \
  /soukrome/ukoly.json /soukrome/gramps-task-plan.json \
  --url https://rodokmen.example.cz --username editor

python3 scripts/family_tree.py gramps tasks push \
  /soukrome/gramps-task-plan.json \
  --url https://rodokmen.example.cz --username editor
```

`plan` podle potřeby naplánuje vytvoření stabilního tagu `ToDo` a pro každý
úkol objekt `Source` plus poznámku, pokud má neprázdný popis. `push` ověří
server, strom, hash plánu, tag i všechny stabilní handles. Zápis je idempotentní:
již přítomné shodné objekty přeskočí a kolizi odmítne. Po vytvoření může
uživatel v Gramps Web změnit stav, prioritu, titul i popis; další plán je
nepřepisuje. Plugin nevytváří úkoly automaticky z `research.json` a neuzavírá
je při vyřešení problému.

## Co se přenáší

Do exportu vstoupí pouze tvrzení se stavem `supported`. Tvrzení v otevřeném
konfliktu se vyloučí; u vyřešeného konfliktu projdou jen výslovně preferovaná
tvrzení. `unverified` a `rejected` se neposílají.

| Místní model | Gramps Web |
|---|---|
| osoba s podporovaným tvrzením | soukromý `Person` |
| `name.given`, `name.surname` | části primárního jména |
| `sex` nebo `person.sex` | pohlaví osoby, jen rozpoznaná hodnota M/F/U |
| `birth.date`, `baptism.date`, `death.date`, `burial.date` | událost s přesným či částečným ISO datem |
| doložený `relationship.parent_child` | rodina, pokud je rodiče možné bezpečně přiřadit jako otce či matku |
| pramen, archiv a citace | `Source`, `Repository`, `Citation` |
| každé přenesené tvrzení a odůvodnění | soukromá výzkumná `Note` |

Pracovní `person.label` se ukládá pouze jako atribut výslovně označený
`FamilyTreeChatGPT working label`, nikoli jako genealogické jméno. Predikát bez
bezpečného strukturovaného mapování se zachová jen ve výzkumné poznámce.
Více odlišných podporovaných hodnot bez explicitního konfliktu se do daného
strukturovaného pole nepřenese a plán vrátí varování.

Stabilní handles a Gramps IDs jsou deterministicky odvozené od typu objektu a
místního ID. Díky tomu lze opakovaně zjistit shodu bez pomocné mapy, ale objekt
se stejným handlem nesmí ručně měnit spravovaným způsobem. Ostatní vzdálená
pole mohou existovat; adaptér je při porovnání ignoruje a nikdy je nemaže.

## Limity první verze

- Soubory pramenů a média se nenahrávají. Plán na ně upozorní; citace a URL
  zůstanou zachované jako metadata.
- Neexistuje `pull`, slučování ani obousměrná synchronizace.
- Adaptér neaktualizuje ani vlastní existující objekt. Shodný přeskočí,
  neshodný označí jako konflikt.
- Nestrukturované vztahy a rodič bez podporovaného tvrzení o pohlaví zůstanou
  pouze v poznámkách účastníků.
- `research.json` zůstává autoritativním badatelským stavem. Gramps Web je
  odvozená soukromá prezentační a kolaborační vrstva.

Před prvním skutečným zápisem použij prázdný testovací strom, vytvoř jeho
zálohu a zkontroluj plán. Vestavěná historie Gramps Web ani tento adaptér
nenahrazují pravidelné zálohy Gramps XML a médií.
