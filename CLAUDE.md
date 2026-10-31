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
| 4. Documentos | próxima | Laudo e atestado (Res. CFP 06/2019) via modelos `.docx` (docxtpl), fluxo rascunho→revisado→aprovado→emitido, hash |

Pós-MVP: consultor IA (API do Claude, texto pseudonimizado) e análise qualitativa → dashboards →
estatística de pesquisa (TCT, AFE/AFC, TRI; depois R via `Rscript`).
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
- Regras de negócio em `siap/`, testadas sem Streamlit. Toda regra nova vem com teste.
- Datas exibidas em dd/mm/aaaa, fuso `America/Sao_Paulo`.

## Pendências do usuário
- Conferir no SATEPSI nome, edição/versão e situação de cada item do inventário (todos entram "não verificado").
- Identificações confirmadas pelo usuário: Pfister, Zulliger, TEPIC-M, TEM-R, R-1.
  "Teste dos Traços" e "TR" ficaram sem identificação: só cadastrar se o usuário lembrar o nome exato.
