# Team-Required Filter — Design Spec

## Problem

Posts irrelevantes (sem relação com futebol) entram no sistema porque o filtro `is_football_post()` usa substring match em termos ambíguos. Exemplo: "eu **jogo** água na calçada" passa porque "jogo" está na lista `FOOTBALL_TERMS`. Combinado com um xingamento ("bosta"), o post recebe rage_score > 0 e entra no banco sem `team_id`.

## Solution

**Exigir `team_id` em todo post.** Um post só é persistido se o sistema conseguir associá-lo a um time, por uma de duas vias:

1. **Menção direta:** O `target_detector` encontra nome/alias de time no texto
2. **Herança via reply:** O post é reply de um post que já temos no banco com `team_id`

Posts sem `team_id` após ambas as tentativas são descartados.

## Changes

### 1. Bluesky Collector (`backend/collector/jetstream.py`)

**`_extract_post`** passa a extrair `reply_to_id` do record do AT Protocol.

O campo `record.reply.parent.uri` contém o URI do post pai no formato `at://did:plc:xxx/app.bsky.feed.post/rkey`. O collector deve **parsear o URI** (split por `/`) para extrair o DID do autor do post pai (que é diferente do DID do post atual) e o rkey, montando o `external_id` no formato `parent_did/parent_rkey`.

Exemplo concreto:
```
URI: at://did:plc:abc123/app.bsky.feed.post/xyz789
→ parent_did = "did:plc:abc123"
→ parent_rkey = "xyz789"
→ reply_to_id = "did:plc:abc123/xyz789"
```

Retorno do dict inclui novo campo:
```python
{
    "external_id": f"{did}/{rkey}",
    "author_handle": did,
    "text": text,
    "created_at": ts,
    "source": "bluesky",
    "reply_to_id": reply_parent_id,  # novo, None se não é reply
}
```

**Twitter e Reddit:** Sem mudança. Já são pré-filtrados por queries de time (Twitter) e subreddits específicos (Reddit). Posts do Reddit/Twitter que passam os filtros atuais mas não mencionam um time específico (ex: post genérico no r/futebol) serão descartados pela nova regra de `team_id` obrigatório. Isso é intencional — o Xingômetro é sobre raiva direcionada a times.

### 2. Post Model (`backend/models/post.py`)

Adicionar campo opcional:
```python
reply_to_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

Armazena o `external_id` do post pai. Não é FK — o post pai pode não existir no banco. String para lookup.

**Migração:** `nullable=True`. Adicionar bloco em `_run_migrations()` (em `main.py`) que verifica se a coluna `reply_to_id` existe na tabela `posts` via `inspector.get_columns("posts")` e, se não, executa `ALTER TABLE posts ADD COLUMN reply_to_id TEXT`. Segue o padrão existente da migração de `coaches.external_id`.

### 3. Pipeline (`backend/main.py`)

Modificar `_process_post()` para:

1. Persistir `reply_to_id` no dict do post (vindo do collector)
2. Após `target_detector.detect()` retornar `team_id = None`:
   - Verificar se post tem `reply_to_id`
   - Se sim, buscar `Post.external_id == reply_to_id` no banco
   - Se post pai existe e tem `team_id` → herdar `team_id`, `match_id` e `coach_id`
3. Se `team_id` continua `None` após ambas as tentativas → **descartar post**

**Herança de reply é single-hop:** Apenas o post pai direto é consultado, sem resolução recursiva de cadeias. Se post C é reply de post B (que foi descartado), post C não conseguirá herdar. Isso é uma limitação aceita — simplifica a implementação e cobre o caso mais comum (reply direto a um post sobre um time).

**Race condition (reply antes do pai):** Se um reply chega antes do post pai ser processado, o lookup não encontrará o pai e o reply será descartado. Isso é um trade-off aceito — na prática, o Jetstream entrega posts em ordem cronológica e o processamento é rápido. Posts perdidos por race condition serão raros e não justificam a complexidade de um buffer/retry.

**Pipeline atualizado:**
```
is_football_post() → match_window ativa?
→ rage_score (descarta se 0)
→ target_detector.detect()
→ SE team_id = None: tenta herdar de reply parent
→ SE team_id ainda = None: DESCARTA
→ valida team_id contra active_teams
→ salva no banco + SSE
```

A busca por `external_id` é O(1) — campo unique indexado.

### 4. Filtro `is_football_post` (`backend/collector/filters.py`)

**Sem mudança.** Continua como pré-filtro grosso para reduzir processamento. A barreira real é a exigência de `team_id`.

## Files Changed

| Arquivo | Tipo | Descrição |
|---|---|---|
| `backend/collector/jetstream.py` | Modificado | Extrair `reply_to_id` do record |
| `backend/models/post.py` | Modificado | Adicionar campo `reply_to_id` |
| `backend/main.py` | Modificado | Herança de team_id via reply + descarte se team_id = None + migração reply_to_id |

## Expected Behavior

| Cenário | Antes | Depois |
|---|---|---|
| Post com menção de time | Aceito | Aceito |
| Reply a post nosso com time | Aceito (sem team_id) | Aceito (herda team_id) |
| Post sem time, não é reply | Aceito (se passou is_football_post) | **Descartado** |
| "eu jogo água na calçada" + xingamento | Aceito (rage 6.0, sem team) | **Descartado** |

## States

- **Loading/Error/Empty:** Sem mudança no frontend — posts descartados simplesmente não aparecem.
- **Logging:** Posts descartados por falta de `team_id` são logados em nível DEBUG com formato: `"Discarded post (no team_id): source=%s external_id=%s"`. Não inclui texto do post para evitar poluição no log.
