# ha-diet-be (Home Assistant – Diet Integration)

Integrazione personalizzata **diet** per Home Assistant:

- persistenza in **SQLite** (aiosqlite),
- **multi-utente** con profili e ACL (lettura per altri, scrittura su se stessi),
- **due cene FREE di default** nel template settimanale,
- servizi HA e **WebSocket API** per il frontend (Angular Material).

> Requisito HA consigliato: **2024.6.0+**

---

## Funzionalità

- **Settimana standard** (template condivisi + default personale).
- **Swap** forward-only dentro la stessa settimana (stesso meal type).
- **Pasti**: 5 slot/giorno (3 obbligatori: colazione, pranzo, cena; 2 opzionali: snack AM/PM).
- **Fame giornaliera** (scala 1–5) e **spuntini** fatti/saltati.
- **Pasti free**: quota settimanale (default 2) con policy `soft`/`hard`.
- **Multi-utente**: ciascuno scrive solo sulla propria dieta; può leggere quella degli altri.
- **Vista comune** (via WS) dei prossimi **pranzo** e **cena** per profili selezionati.
- **Sensori**: fame media 7 giorni, snack completati oggi, free usati in settimana.

---

## Installazione

1. Copia la cartella `custom_components/diet` in:
   <config>/custom_components/diet

2. Riavvia Home Assistant.
3. (Opzionale) Installa via **HACS** come _Custom Repository_:

- Tipo: **Integration**
- Aggiungi questo repository e installa.

4. Aggiungi il frontend (separato) come pannello personalizzato che usa le WebSocket API esposte.

---

## Servizi

- `diet.apply_week_template({ owner_profile_id, start_date, template_id? })`
- `diet.swap_meal({ owner_profile_id, date_from, date_to, meal_type })`
- `diet.set_snack({ owner_profile_id, date, period, done })`
- `diet.set_hunger({ owner_profile_id, date, score })`
- `diet.set_choice({ owner_profile_id, date, meal_type, source, title?, notes? })`

> Le chiamate di **scrittura** richiedono che l’utente HA chiamante sia il **proprietario** (`owner_profile_id`) oppure disponga di ACL `can_write=1`.

---

## WebSocket API

- `diet/get_capabilities` → profilo soggetto + elenco profili con `can_read/can_write`
- `diet/get_day { owner_profile_id, date }` → dettaglio giorno
- `diet/get_week { owner_profile_id, start_date }` → 7 giorni (normalizzati al lunedì)
- `diet/get_next_meals { owner_profile_ids: number[], horizon_hours?: number }` → prossimi pranzo/cena

---

## Database (SQLite)

- `diet_profiles`, `profile_acl`
- `week_templates`, `template_meals` (`default_source: 'proposed'|'free'|'skipped'`)
- `template_meal_alternatives`
- `plan_days`, `day_meals`, `snacks`, `free_meals`, `swaps`

Schema version: **SCHEMA_VERSION = 5**

---

## Sensori

- `sensor.diet_hunger_score_(profilo)` — media mobile 7 giorni (1–5)
- `sensor.diet_snacks_today_(profilo)` — spuntini fatti oggi (0..2)
- `sensor.diet_free_meals_week_(profilo)` — conteggio free nella settimana corrente

---

## Note su Template

- **Condivisi** per default (`week_templates.profile_id = NULL`).
- **Default personale** per ciascun profilo (un template attivo legato al profilo).
- Due **cene FREE** pre-impostate nel template (nessuna proposta, conteggiate nella quota).

---

## Gestione profili e ACL

L’integrazione **non crea utenti propri**, ma si sincronizza con quelli di **Home Assistant**.

I profili (`diet_profiles`) vengono generati automaticamente a partire dagli **utenti HA attivi**.  
Le ACL sono configurate di default come:

| Relazione    | Lettura | Scrittura |
| ------------ | ------- | --------- |
| Sé stesso    | ✅      | ✅        |
| Altro utente | ✅      | ❌        |

Questa logica consente:

- a ciascun utente di **gestire solo la propria dieta**;
- di **visualizzare** (in sola lettura) la dieta degli altri utenti.

---

### 🔁 Servizio di sincronizzazione profili

Quando aggiungi o rimuovi utenti in Home Assistant, puoi riallineare i profili tramite il servizio:

#### `diet.sync_profiles_from_ha`

Sincronizza la tabella `diet_profiles` e imposta le ACL incrociate in sola lettura.

#### Parametri opzionali

| Parametro        | Tipo   | Default | Descrizione                                                                                |
| ---------------- | ------ | ------- | ------------------------------------------------------------------------------------------ |
| `prune_missing`  | `bool` | `false` | se `true`, rimuove profili che non esistono più in HA (⚠️ cancella anche i dati associati) |
| `include_system` | `bool` | `false` | se `true`, include anche utenti di sistema                                                 |

#### Esempio YAML

```yaml
service: diet.sync_profiles_from_ha
data:
  prune_missing: false
  include_system: false


## Licenza

MIT © 2025
```
