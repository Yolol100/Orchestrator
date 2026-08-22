# Webactueel GitHub Orchestrator

Generieke GitHub-transportlaag voor repositoryplannen die al door `webactueel-workflow` zijn gekozen en gevalideerd. Deze repository is **geen inhoudelijke controller** en bevat geen SEO-, WordPress-, Elementor-, Design-, Leads- of QA-beslislogica.

## Wat hij doet

1. Ontvangt één immutable dispatcherrequest op een tijdelijke `runtime/**` branch.
2. Controleert workflow-ID, generation, approval, dependency-receipts en de exacte adapter-registry fingerprint.
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

De blueprint splitst least-privilege tokens per transportvorm: gewone request-file adapters krijgen alleen `contents: write`; de guarded WordPress request-PR adapter krijgt op alleen `wordpressconnector` `contents: write` + `pull_requests: write`. Het gewone workflow-`GITHUB_TOKEN` blijft `contents: read` voor deze repository. WordPress-runtimecredentials blijven uitsluitend in `wordpressconnector` en worden pas door de trusted `wordpress-execute.yml` op `main` gebruikt.

Voor de huidige standaard WordPress-route is geen VPS of persistente self-hosted GitHub runner nodig. Vereist zijn een private `wordpressconnector` repository, exact `WPCONNECTOR_TRUSTED_REQUEST_ACTOR`, een geïnstalleerde WordPress Connector-plugin, `WPCONNECTOR_SITE_URL` op HTTPS, `WPCONNECTOR_REST_USERNAME`, `WPCONNECTOR_REST_APPLICATION_PASSWORD`, een geslaagde authenticated healthcheck en de taakrelevante WordPress Connector safety gates.

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
- `elementorjson` is bewust niet generiek dispatchbaar zolang het huidige adaptercontract geen sterke requestcorrelatie exposeert.
- `wordpressconnector` gebruikt bewust een request-PR op een tijdelijke branch; de Orchestrator verandert dit niet in een gewone pushroute en een WordPress-runtime node vereist `approval_before_write` of strenger. De PR-workflow is een secretless guard; de echte uitvoering gebeurt daarna via `wordpress-execute.yml` vanaf vertrouwde `main` op GitHub-hosted `ubuntu-latest` over authenticated HTTPS REST.
- `transcriberen` gebruikt zijn eigen append-only `runtime-requests` queue; de dispatcher maakt daarvoor geen nieuwe runtimebranch.
- Klant-/projectwaarheid hoort niet op `main`. Tijdelijke runtimebranches worden pas na readback/acceptatie opgeruimd.
- Een groene GitHub Action bewijst transport, niet vakinhoudelijke correctheid.

## Lokale controle

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/*.py tests/*.py
```

Gebruik daarna een echte staging-/read-only smoke voordat write- of releasepaden worden toegestaan.

## Opruimen van tijdelijke runtimebranches

Na controller-closure kun je `python3 scripts/cleanup_runtime_branches.py transport-plan.json --confirm-workflow-id <WF-ID>` uitvoeren. De helper verwijdert alleen `runtime/*` branches waarvan de huidige SHA exact overeenkomt met de transportreceipt; verplaatste of vaste branches worden geweigerd.
