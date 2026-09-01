# Webactueel GitHub Orchestrator

> **Portfoliostatus:** Flagship · actieve infrastructuur · Webactueel-transportlaag

## In één oogopslag

De Orchestrator transporteert reeds goedgekeurde Webactueel-repositoryplannen naar begrensde specialistadapters. Hij neemt geen vakbeslissingen over en beschouwt een gestarte workflow nooit automatisch als geaccepteerd resultaat.

| Onderdeel | Bewijs |
| --- | --- |
| Doelgroep | Webactueel-controllers en geregistreerde specialistrepositories |
| Stack | Python, GitHub Actions, GitHub App-tokens en JSON-contracten |
| Kwaliteit | Compilechecks, unittests, registry-fingerprintvalidatie en idempotency |
| Veiligheid | Kortlevende least-privilege tokens per transportvorm |
| Resultaat | Correlatievast `transport-plan.json` plus expliciete cleanupverplichtingen |

## Architectuur

```text
Webactueel-controller
        ↓ immutable request + approval_policy + dependency receipts
Orchestrator → adapterregistry ─┬→ tijdelijke runtimebranch/request-PR
        ↓                       └→ bestaande append-only branch (transcriberen)
transport-plan.json                         ↓
        └──────── specialistartifact/result → readback + vakacceptatie ────────┘
```

## Snel starten

Gebruik de [requestprocedure](#request-starten), wacht op de Actions-run en laat de owning controller daarna artifact, correlatie en vakinhoud accepteren. Een groene transportworkflow is geen inhoudelijke goedkeuring.

Generieke GitHub-transportlaag voor repositoryplannen die al door `webactueel-workflow` zijn gekozen en gevalideerd. Deze repository is **geen inhoudelijke controller** en bevat geen SEO-, WordPress-, Elementor-, Design-, Leads- of QA-beslislogica.

## Wat hij doet

1. Ontvangt één immutable dispatcherrequest op een tijdelijke `runtime/**` branch.
2. Controleert workflow-ID, generation, approval policy, dependency-receipts en de exacte adapter-registry fingerprint.
3. Beperkt een kortlevend GitHub App-token dynamisch tot alleen de repositories in dat request.
4. Schrijft alleen controller-ready requestbestanden naar geregistreerde specialistadapters.
5. Start geen downstream node alleen omdat een upstream node net is aangeroepen.
6. Produceert `transport-plan.json` met head-SHA's, event-ID's, requestlocators en cleanup-verplichtingen.
7. Geeft de workflow terug aan `webactueel-workflow` voor readback, vakacceptatie en de volgende generation.

## Benodigd

De huidige Webactueel-deployment gebruikt `Yolol100/Orchestrator`. Installeer de GitHub App uitsluitend op de specialistrepositories die de controller mag bedienen.

Repository variable:

- `WEB_ACTUEEL_APP_CLIENT_ID`

Actions secret:

- `WEB_ACTUEEL_APP_PRIVATE_KEY`

De blueprint splitst least-privilege tokens per transportvorm: gewone request-file adapters krijgen alleen `contents: write`; de guarded WordPress request-PR adapter krijgt op alleen `wordpressconnector` `contents: write` + `pull_requests: write`. Het gewone workflow-`GITHUB_TOKEN` blijft `contents: read` voor deze repository.

## Request starten

Voorkeursroute vanuit ChatGPT/GitHub connector:

1. Maak vanaf `main` een tijdelijke branch zoals `runtime/wf-abcdef123456-g1`.
2. Voeg precies één nieuw bestand toe onder `requests/queue/<request-id>.json`.
3. De push start `.github/workflows/orchestrate.yml`.
4. Lees na afloop het artifact `webactueel-transport-<run_id>`.
5. Correlatie en inhoudelijke acceptatie gebeuren daarna door de controller/owner.

`workflow_dispatch` is alleen bedoeld voor handmatige replay van een bestaand requestbestand op de geselecteerde ref. Idempotency voorkomt dubbele side effects.

## Belangrijke grenzen

- `invoked` is nooit hetzelfde als `accepted`.
- Een dependency is alleen voldaan wanneer het request een controller-issued `dependency_receipt` bevat.
- `elementorjson` gebruikt uitsluitend de geregistreerde gecorreleerde request-file-route via `requests/runtime.json`; dit is geen vrije generieke dispatchroute en acceptatie vereist de exacte request-/resultcorrelatie.
- `wordpressconnector` gebruikt bewust een request-PR op een tijdelijke branch; de Orchestrator verandert dit niet in een gewone pushroute en een WordPress-runtime node vereist `approval_before_write` of strenger.
- `transcriberen` gebruikt zijn eigen append-only `runtime-requests` queue; de dispatcher maakt daarvoor geen nieuwe runtimebranch.
- Klant-/projectwaarheid hoort niet op `main`. Tijdelijke runtimebranches worden pas na readback/acceptatie opgeruimd.
- Een groene GitHub Action bewijst transport, niet vakinhoudelijke correctheid.

## Lokale controle

Deze commando's zijn ook de CI-bron. De Runme Action voert exact dezelfde benoemde Markdown-cellen uit, zodat README en CI niet uit elkaar gaan. Runme is lokaal optioneel; de commando's blijven gewone shellcommando's.

```bash {"name":"compile-python"}
python3 -m py_compile scripts/*.py tests/*.py
```

```bash {"name":"regression-tests"}
python3 -m unittest discover -s tests -v
```

Gebruik daarna een echte staging-/read-only smoke voordat write- of releasepaden worden toegestaan.

## Opruimen van tijdelijke runtimebranches

Na controller-closure kun je `python3 scripts/cleanup_runtime_branches.py transport-plan.json --confirm-workflow-id <WF-ID>` uitvoeren. Gewone requestbranches worden alleen verwijderd wanneer de huidige SHA nog exact overeenkomt met de transportreceipt. Een guarded WordPress request-PR mag na gevalideerde result-writeback bewust zijn verplaatst; lever daarvoor een apart controller-geverifieerd JSON-bestand aan met `--verified-heads verified-heads.json`, bijvoorbeeld `{"Yolol100/wordpressconnector:runtime/...": "<current-40-hex-sha>"}`. Zonder die expliciete actuele SHA faalt cleanup gesloten. Vaste branches worden nooit verwijderd.

## Projectstatus, roadmap en support

De transportlaag is actief en contractgestuurd. Uitbreidingen vereisen een geregistreerde adapter, testbewijs en expliciete controlleracceptatie. Meld reproduceerbare defecten via [GitHub Issues](https://github.com/Yolol100/Orchestrator/issues); plaats daar nooit private keys, tokens of requestpayloads met klantdata.

## Licentie

Deze repository bevat momenteel geen open-sourcelicentie. Hergebruik, distributie of afgeleide werken zijn niet toegestaan zonder expliciete toestemming van de rechthebbende.
