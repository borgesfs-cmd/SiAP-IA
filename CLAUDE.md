# SIAP-IA — instruções para o Claude

Sistema Inteligente de Avaliação Psicológica. **Uso pessoal e não comercial** de uma psicóloga/psicólogo.
Leia `docs/DOCUMENTO_MESTRE.md` antes de propor mudanças de escopo. Histórico em `docs/HISTORICO_CONVERSA.md`.

## Regras inegociáveis
1. **A IA e o sistema auxiliam; não decidem.** Nada de aptidão, diagnóstico ou emissão de documento automáticos.
   Documentos psicológicos permanecem rascunho até aprovação explícita do profissional.
2. **SATEPSI:** a única porta de liberação de uso profissional é `siap.catalogo.pode_uso_profissional`
   (regra em `siap/satepsi.py`). Nenhuma tela ou módulo pode contorná-la. Sem verificação, desfavorável,
   restrito, em avaliação, não localizado ou verificação vencida ⇒ **bloqueado**.
3. **Verificações SATEPSI e auditoria são somente inclusão.** Não criar funções de editar/apagar.
   Correção = nova verificação. Toda alteração de dados chama `auditar(...)` na mesma transação.
4. **Sem identificação direta de pessoas avaliadas.** Nunca criar campos de nome, CPF, RG, endereço,
   telefone, e-mail ou foto de avaliando. Usar código (ex.: `AV-2026-001`). Datas de nascimento: preferir idade.
   **Nome em documentos psicológicos:** nos textos usa-se sempre o marcador `{{NOME DA PESSOA AVALIADA}}`
   (`siap.documentos.TOKEN_NOME`). O nome real é digitado só no momento de baixar o `.docx`, substitui o marcador
   apenas no arquivo gerado (`siap.exportar_docx.gerar_docx`) e é descartado: nunca vai para banco, backup,
   auditoria, logs, hash ou API externa. Para baixar de novo, digita-se outra vez. Não criar nenhum recurso que
   memorize esse nome (nem "lembrar último nome"). A página Documentos exibe essa instrução ao usuário.
5. **Nada de material protegido:** não implementar itens, estímulos, manuais, tabelas normativas ou chaves
   de correção de testes comerciais. Resultados clínicos são *registrados* a partir do manual/plataforma
   oficial (escore bruto, percentil, classificação + referência), não *calculados* pelo sistema.
6. **IA não inventa números.** Toda saída de IA separa "calculado pelo sistema" de "interpretação sugerida".
   Texto enviado a API externa deve estar pseudonimizado.
7. Não registrar segredos no repositório (`.streamlit/secrets.toml` está no `.gitignore`).

## Escopo atual (MVP)
| Etapa | Situação | Conteúdo |
|---|---|---|
| 1. Base | ✅ | Streamlit, SQLAlchemy (SQLite local / PostgreSQL na nuvem), auditoria, testes, CI |
| 2. Catálogo + SATEPSI | ✅ | Instrumentos, versões, verificação assistida com evidência e validade, bloqueio |
| 3. Avaliações | ✅ | Finalidades (padrão + manuais), caso codificado, entrevistas/observações, instrumentos aplicados (só versões elegíveis **para a finalidade**), resultados transcritos, alertas |
| 4. Documentos | ✅ | Laudo, atestado, relatório, parecer e declaração (estrutura Res. CFP 06/2019); rascunho só com dados registrados; marcadores `[[...]]` bloqueiam aprovação; rascunho→revisado→aprovado (confirmação de autoria)→emitido (conteúdo congelado + SHA-256); retificação; `.docx` |

| A. Consultor IA + qualitativa | ✅ | Consultor metodológico, revisão de redação, sugestão de códigos (API do Claude, `claude-opus-5-5`, structured outputs, fallback de recusa); livro de códigos, codificação de trechos literais, matriz e evidências |

| B. Painéis | ✅ | Visão geral (contagens, mês, finalidade, instrumentos, SATEPSI, vencimentos), avaliação individual (percentis transcritos + linha do tempo), comparativo entre avaliações; Altair, cor única, tabela em cada gráfico |

| C. Estatística de pesquisa | ✅ | Conjuntos anonimizados (CSV/XLSX, checagem de identificadores), descritivas, alfa (IC Feldt) e ômega, análise de itens, AFE (eixos principais, varimax/promax, KMO, Bartlett, análise paralela), AFC (ML, validada contra lavaan), TRI 2PL e GRM (`girth`) |
| D. Restauração de backup | ✅ | Aba Restaurar: validação, resumo, cópia prévia, confirmação digitada, restauração transacional |
| E. Exportações e biblioteca | ✅ | PDF dos documentos; registro documental por avaliação (Word/PDF); biblioteca de modelos e frases; relatório de pesquisa APA (Word/PDF) |

**Gerador de documentos (`siap/render.py`):** todo arquivo exportado é montado em blocos (`Titulo`, `Secao`,
`Paragrafo`, `Lista`, `Tabela` APA, `Assinatura`…) e renderizado por `para_docx`/`para_pdf` (fpdf2 + Liberation Sans
em `static/fontes`, licença OFL). O marcador de nome é substituído só ali. Novos relatórios devem usar esse módulo.
`siap/registro_documental.py` (guarda documental), `siap/biblioteca.py` (trechos; inserção via `salvar_secoes`),
`siap/relatorio_pesquisa.py` (APA: `num(..., sem_zero=True)` para estatísticas ≤ 1). Ao alterar o texto de uma
seção fora do formulário do editor, remova `st.session_state[f"sec_{id}"]` para o editor recarregar.

**AFC (`estatistica.afc`):** implementação própria por ML (estrutura simples, variância dos fatores = 1, divisor N,
χ² = N·F como no lavaan); CFI, TLI, RMSEA (IC 90%), SRMR, EP pela informação esperada. Validada contra o lavaan com
Holzinger & Swineford (1939) em `tests/dados/` — esse teste não pode ser afrouxado. Não usar `semopy` (não compila).

**Backup (`siap/backup.py`):** restauração substitui tudo numa transação, valida antes de apagar, preserva
`segredos_cifrados`, ajusta sequências no PostgreSQL. Ao criar tabela nova, ela entra no backup automaticamente
(gera-se a partir de `Base.metadata`); se for sensível como segredos, inclua-a em `PRESERVADAS` e exclua do export.

**Estatística (`siap/estatistica.py`):** implementação própria de PAF, varimax, promax (como `stats::promax`), KMO,
Bartlett e análise paralela — NÃO reintroduzir `factor_analyzer` (incompatível com scikit-learn ≥ 1.8). Toda rotina
nova precisa de teste que recupere parâmetros conhecidos de dados simulados (`tests/test_estatistica.py`).
Resultados são rotulados "calculado pelo sistema" e vêm com alertas de pressupostos.

**Chave da API (`siap/segredos.py`, aba 🔑):** a usuária cola a chave; ela é testada (`models.retrieve`, sem custo),
cifrada com Fernet + scrypt sobre `APP_PASSWORD` (ou `SIAP_CHAVE_MESTRA`) e guardada em `segredos_cifrados`.
Nunca exibir inteira, nunca pôr em backup/auditoria/logs. `ANTHROPIC_API_KEY` nos Secrets tem prioridade.
**Painéis (`siap/paineis.py`):** só contagens e valores transcritos; percentil entra no gráfico apenas se o texto for
número simples 0–100 (`percentil_numerico`). Referência visual com `mark_tick` (o tema do Streamlit oculta
`mark_rule` em camadas).

**Consultor IA (`siap/ia.py`):** desligado até consentimento (perfil.ia_habilitada) + `ANTHROPIC_API_KEY` nos Secrets.
Todo envio passa por `ia.pseudonimizar` (nome→[PESSOA AVALIADA], código→[CASO], CPF/e-mail/telefone→[REMOVIDO]).
Saídas são sugestões: nada é gravado sem clique da profissional. Instrumentos sugeridos são filtrados pela lista de
elegíveis (SATEPSI + finalidade). Trechos sugeridos para codificação só valem se forem literais. Números novos na
resposta são sinalizados. A auditoria guarda só metadados (função, modelo, tokens). Testes usam cliente falso —
nunca chamar a API real nos testes.
**Fora do escopo por decisão do usuário:** aprendizado de máquina; funcionalidades comerciais.

Finalidades: padrões (Psicodiagnóstico, Avaliação neuropsicológica, Trânsito, Porte/posse de arma, Seleção,
Treinamento e desenvolvimento, Pesquisa) + incluídas pelo usuário. Nunca apagar: só desativar.
Uma verificação SATEPSI vale para todas as finalidades ou só para as selecionadas; `pode_uso_profissional(...,
finalidade_id=...)` aplica isso. A finalidade de uma avaliação não muda depois de haver instrumento registrado.
Avaliação concluída/cancelada é somente leitura até ser reaberta.

## Estrutura
- `app.py` — entrada: senha (`APP_PASSWORD`) e navegação.
- `paginas/` — telas Streamlit (sem regra de negócio).
- `siap/models.py` — tabelas; `siap/satepsi.py` — regra pura; `siap/catalogo.py` — catálogo, SATEPSI, auditoria, backup;
  `siap/finalidades.py`; `siap/avaliacoes.py` — avaliações + filtro de identificadores (CPF/e-mail/telefone);
  `siap/documentos.py` — documentos e fluxo; `siap/exportar_docx.py` — geração do Word;
  `siap/ia.py` — consultor IA; `siap/segredos.py` — chave da API cifrada; `siap/qualitativo.py` — análise qualitativa;
  `siap/paineis.py` — agregações dos painéis; `siap/backup.py` — restauração; `siap/estatistica.py` + `siap/pesquisa.py` — estatística de pesquisa;
  `siap/inventario.py` — inventário inicial; `siap/db.py` — conexão + migrações; `siap/ui.py` — utilidades de tela
  (`executar` para ações de formulário).
- `siap/migracoes/` — Alembic. Aplicadas automaticamente ao abrir o app.
- `tests/` — pytest (regras, serviços, persistência, páginas via `streamlit.testing`).

## Comandos
```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
streamlit run app.py
```
Banco: `DATABASE_URL` (env ou secrets do Streamlit); sem ela, SQLite em `data/siap.db`.
**Mudou um modelo?** Gere a migração com `python scripts/nova_migracao.py "descrição"`, revise o arquivo e rode
`pytest` (`tests/test_migracoes.py` falha se modelos e migrações divergirem). Nunca edite migração já publicada.

## Convenções
- Interface, mensagens, nomes de domínio e documentação em **português**.
- **Interface (padrão visual):** tema em `.streamlit/config.toml` (claro/escuro, fonte Inter, índigo `#5552d9`);
  menu agrupado por áreas em `app.py` com ícones `:material/...:`; toda página começa com
  `iniciar_pagina(titulo, descricao, icone, ajuda=[passos])` (cabeçalho + botão “Como usar”). Use os componentes de
  `siap/ui.py`: `cartao_acao`, `estado_vazio`, `passos` (indicador de etapas), `rodape`. Prefira elementos clicáveis:
  `st.pills`/`st.segmented_control` para poucas opções, `st.dialog` para criar registros, `st.dataframe(on_select=...)`
  para abrir um item clicando na linha, `st.page_link`/`st.switch_page` para levar a próxima ação. Placeholders e
  rótulos sempre em português. Página inicial: `paginas/inicio.py` + `siap/inicio.py` (primeiros passos, avisos,
  atividade recente).
- Regras de negócio em `siap/`, testadas sem Streamlit. Toda regra nova vem com teste.
- Datas exibidas em dd/mm/aaaa, fuso `America/Sao_Paulo`.

## Pendências do usuário
- Conferir no SATEPSI nome, edição/versão e situação de cada item do inventário (todos entram "não verificado").
- Identificações confirmadas pelo usuário: Pfister, Zulliger, TEPIC-M, TEM-R, R-1.
  "Teste dos Traços" e "TR" ficaram sem identificação: só cadastrar se o usuário lembrar o nome exato.
