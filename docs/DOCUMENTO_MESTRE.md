# SIAP-IA — Documento Mestre v1.9

**Versão 1.9 · 31/10/2026 · Escopo: uso pessoal e não comercial**
Substitui a v1.0 (Word). Consolida decisões e requisitos. Este documento não comprova a situação regulatória de nenhum instrumento e não substitui verificação normativa atualizada.

## v1.9 (Exportações e biblioteca)
- **PDF direto** dos documentos psicológicos (além do Word), com a mesma aparência, paginação e código de integridade.
- **Registro documental** de cada avaliação (Word/PDF): identificação codificada, demanda, registros, instrumentos e resultados, análise qualitativa, documentos (com o texto emitido) e histórico — para guarda pelo prazo do CFP.
- **Biblioteca de modelos e frases**, com inserção em um clique nas seções dos documentos.
- **Relatório de pesquisa** (Word/PDF) com tabelas no padrão APA, método descritivo e referências.
- Correção: aplicar sugestão da IA agora atualiza o editor (antes o texto antigo podia sobrescrever a sugestão).

## v1.8 (AFC e restauração)
- **AFC** por máxima verossimilhança, com CFI, TLI, RMSEA (IC 90%), SRMR, cargas, erros-padrão e correlações entre fatores; atalho para usar a estrutura da AFE. **Validação:** reproduz exatamente os resultados publicados do lavaan (R) para Holzinger & Swineford (1939): χ² = 85,306 (gl = 24), CFI = 0,931, TLI = 0,896, RMSEA = 0,092 [0,071; 0,114], SRMR = 0,065.
- **Restauração de backup** na própria tela: valida o arquivo, mostra o resumo, oferece cópia do estado atual, exige confirmação digitada e restaura tudo numa única transação (a chave da API é preservada).

## v1.7 (Interface)
- Redesenho visual a pedido da usuária: tema próprio (claro e escuro), menu por áreas com ícones, página inicial com ações rápidas, primeiros passos, avisos e atividade recente; botão “Como usar” em todas as páginas; nova avaliação em janela com botões de escolha; etapas e próximo passo sugerido na avaliação; listas clicáveis; atalho do catálogo para a verificação SATEPSI; tipos de documento em cartões.

## v1.6 (Pós-MVP C)
- **Estatística de pesquisa:** importação de bases anonimizadas (CSV/XLSX; recusa colunas e valores identificadores), descritivas e frequências, precisão (alfa com IC de Feldt, alfa padronizado, ômega de McDonald, análise de itens), AFE (eixos principais; varimax/promax; KMO; Bartlett; análise paralela de Horn) e TRI (2PL e resposta graduada).
- Validação: as rotinas recuperam parâmetros conhecidos de dados simulados (ômega teórico, estrutura de dois fatores, parâmetros 2PL).
- **AFC adiada:** a biblioteca candidata não compila de forma confiável; será feita depois via R (lavaan) ou outra biblioteca validada.

## v1.5 (Pós-MVP B)
- **Aba 🔑 Chave da API:** a chave do Claude é colada no próprio sistema, testada, guardada criptografada (derivada da senha do app) e nunca exibida inteira nem incluída no backup.
- **Painéis:** visão geral, avaliação individual (percentis transcritos e linha do tempo) e comparativo entre avaliações. Sem cálculo de normas.

## v1.4 (Pós-MVP A)
- **Consultor IA** (API do Claude): consultor metodológico, revisão de redação de seções de documentos e sugestão de códigos qualitativos. Fica desligado por padrão; ativa-se com termo de consentimento e chave `ANTHROPIC_API_KEY`. O texto é pseudonimizado, as respostas são só sugestões, números novos são sinalizados e a auditoria guarda apenas metadados.
- **Análise qualitativa:** livro de códigos com definição operacional, codificação de trechos literais (manual ou sugestão da IA aceita), matriz código × registro e evidências por código.

## v1.3 (Etapa 4)
- Documentos psicológicos implementados (laudo, atestado, relatório, parecer, declaração), com fluxo de aprovação, emissão com SHA-256, retificação e exportação .docx.
- **Regra do nome da pessoa avaliada** formalizada (seção 7-A) e exibida como instrução fixa no sistema.

## v1.2 (Etapa 3)
- Finalidades: Psicodiagnóstico e Avaliação neuropsicológica incluídas entre as padrão; **inclusão manual de outras finalidades**.
- Liberação SATEPSI por finalidade; Etapa 3 implementada; migrações de banco com Alembic.

## O que mudou da v1.0 para a v1.1
| Tema | v1.0 | v1.1 |
|---|---|---|
| Escopo | 10 módulos / 10 fases | **MVP em 4 etapas**; demais módulos após o MVP |
| Aprendizado de máquina | Módulo 04 | **Retirado** |
| Laboratório psicométrico | Único módulo | **Separado**: registro de resultados clínicos (Etapa 3) × estatística de pesquisa (pós-MVP) |
| Execução | Local (Streamlit + SQLite) | **Nuvem**: Streamlit Community Cloud + PostgreSQL (Neon); SQLite só em testes |
| Identificação | Dados sensíveis protegidos | **Sem identificação direta** de avaliandos: apenas códigos |
| SATEPSI | Verificação assistida | Assistida **com evidência obrigatória para favorável e validade** (padrão 90 dias) |
| Documento Mestre | Arquivo Word fora do código | Markdown versionado no repositório + `CLAUDE.md` |

## 1. Visão e escopo
SIAP-IA: apoio ao trabalho de avaliação psicológica em psicodiagnóstico adulto e infantil, seleção e treinamento, trânsito e porte de arma de fogo, e pesquisa. Integra catálogo de instrumentos, conformidade SATEPSI, gestão de avaliações, documentos psicológicos e, depois do MVP, consultoria por IA, análise qualitativa, dashboards e estatística de pesquisa.

## 2. Princípios
1. A IA auxilia; não decide aptidão, diagnóstico, afastamento ou emissão de documento.
2. Nenhum avaliando é identificado diretamente: o sistema usa códigos. A correspondência código↔pessoa fica fora do sistema.
3. Não se implementam itens, estímulos, manuais, normas ou chaves de correção protegidos. Resultados clínicos são **registrados** a partir das fontes oficiais.
4. Cálculos estatísticos vêm de rotinas testadas e reprodutíveis. A IA nunca cria números.
5. Rastreabilidade: auditoria somente de inclusão; histórico SATEPSI imutável.
6. Desenvolvimento e testes apenas com dados sintéticos.

## 3. Arquitetura
- **Aplicação:** Python 3.12 + Streamlit (multipáginas), regras de negócio no pacote `siap/`, independentes da interface.
- **Dados:** SQLAlchemy 2. PostgreSQL (Neon) em produção, SQLite em testes. Migrações com Alembic quando o esquema mudar.
- **Acesso:** app privado no Streamlit Cloud + senha própria (`APP_PASSWORD`).
- **Qualidade:** pytest + GitHub Actions a cada envio.
- **Futuro:** API do Claude com texto pseudonimizado (consultor/redação), `docxtpl` para documentos, R via `Rscript` para psicometria avançada.

## 4. Plano de implementação
| Etapa | Entrega | Situação |
|---|---|---|
| 1. Base | Repositório, app, banco, auditoria, testes, CI, implantação em nuvem | ✅ concluída |
| 2. Catálogo + SATEPSI | Instrumentos/versões, verificação com evidência e validade, bloqueio, backup | ✅ concluída |
| 3. Avaliações | Finalidades (padrão + manuais), caso codificado, entrevistas e observações, instrumentos aplicados (somente versões elegíveis para a finalidade), resultados transcritos, alertas de conformidade | ✅ concluída |
| 4. Documentos | Laudo, atestado, relatório, parecer e declaração; rascunho → revisado → aprovado → emitido; retificação; .docx; SHA-256 | ✅ concluída |
| Pós-MVP A | Consultor IA metodológico e de redação; análise qualitativa (codificação, matrizes, evidências) | ✅ concluída |
| Pós-MVP B | Dashboards | ✅ concluída |
| Pós-MVP C | Estatística de pesquisa: descritivas, TCT, precisão, AFE, TRI (AFC adiada) | ✅ concluída |

## 5. Inventário inicial (candidatos, todos "não verificado")
| Categoria | Instrumentos |
|---|---|
| Personalidade / expressivos | Pirâmides Coloridas de Pfister; Zulliger; Palográfico |
| Atenção | BPA; AC; TEACO-FF; TEADI; TEALT; d2 e d2-R (versões independentes) |
| Inteligência / raciocínio | R-1; G-36; G-38 |
| Memória | TEM-R; TEPIC-M |

"Teste dos Traços" e "TR" saíram do inventário por falta de identificação. Podem ser cadastrados pelo próprio sistema quando o nome exato for lembrado.

## 6. Política SATEPSI (implementada)
- A situação é avaliada **por versão**. A verificação que vale é a de data de consulta mais recente.
- **Elegível** somente se: situação favorável **e** consulta dentro da validade **e** evidência anexada.
- **Bloqueado** se: sem verificação; desfavorável; restrito/com condições; em avaliação; não localizado; verificação vencida; data inconsistente.
- Verificações nunca são editadas ou apagadas. Corrigir significa registrar nova consulta.
- O bloqueio não apaga dados nem altera documentos já emitidos. Situações anteriores exigem análise profissional.
- Não se presume API pública do SATEPSI.
- Cada verificação vale para **todas as finalidades** ou **somente as selecionadas** (ex.: listas normativas de trânsito ou porte de arma). Fora delas, a versão fica bloqueada para aquela finalidade.
- A aplicação registrada guarda a situação SATEPSI e a verificação vigente no momento do registro.
- Se uma versão perder a elegibilidade, as avaliações em andamento que a usaram recebem alerta no Panorama e na própria avaliação. Nada é apagado.

## 6-A. Finalidades e avaliações (implementado)
- Finalidades padrão: Psicodiagnóstico; Avaliação neuropsicológica; Trânsito (CNH); Porte/posse de arma de fogo; Seleção de pessoal; Treinamento e desenvolvimento de pessoal; Pesquisa. Você pode **incluir outras**, editar e desativar (sem apagar).
- Avaliação: código automático AV-AAAA-NNN; finalidade; faixa etária; idade; escolaridade; contexto/solicitante; demanda; situação (em andamento / concluída / cancelada).
- Registros: entrevista inicial, anamnese, entrevista, observação, contato com fonte complementar, devolutiva, outro. Edições guardam a versão anterior na auditoria.
- Resultados: medida, escore bruto, escore padronizado, percentil, classificação e **referência obrigatória** (manual/tabela/plataforma). O sistema não calcula normas.
- Privacidade: textos com padrão de CPF, e-mail ou telefone são recusados. Nomes próprios não são detectáveis automaticamente.

## 7. Documentação psicológica (Etapa 4, implementada)
- Tipos e seções (estrutura baseada na Res. CFP 06/2019; conferir com a versão vigente antes do uso real):
  - **Laudo:** identificação, descrição da demanda, procedimento, análise, conclusão, referências (obrigatórias).
  - **Relatório:** identificação, demanda, procedimento, análise, conclusão (referências opcionais).
  - **Parecer:** identificação, demanda, análise, conclusão, referências.
  - **Atestado:** identificação e texto.
  - **Declaração:** texto com informações objetivas (alerta se mencionar diagnóstico, sintomas ou CID).
- O rascunho é montado **só com dados registrados**: demanda, procedimentos com datas, resultados transcritos e referências informadas. **Análise e conclusão são redigidas pela(o) profissional.** O sistema não interpreta nem conclui.
- Trechos `[[...]]` indicam o que falta completar e **bloqueiam a aprovação**.
- Fluxo: **rascunho → revisado → aprovado → emitido**.
  - A aprovação exige confirmar a revisão integral e a autoria técnica.
  - Editar um documento revisado ou aprovado devolve-o a rascunho.
  - A emissão congela o conteúdo e grava um SHA-256, impresso no rodapé.
  - Documento emitido não muda: corrige-se por **retificação** (novo documento que referencia o anterior).
- Exportação `.docx`: Arial 12, numeração "Página X de Y", local e data por extenso, bloco de assinatura com CRP. Prévias saem com a marca "RASCUNHO". Para PDF, usar "Exportar como PDF" no Word ou no Pages.
- Dados profissionais (nome, CRP, titulação, cidade) ficam num perfil único.

## 7-A. Regra do nome da pessoa avaliada (instrução do sistema)
1. O SIAP-IA **não grava** o nome de quem é avaliado. Nos textos dos documentos aparece o marcador `{{NOME DA PESSOA AVALIADA}}`.
2. O nome é digitado **apenas no momento de baixar o arquivo Word** e substitui o marcador **somente no arquivo gerado**.
3. Depois do download, o campo é **apagado automaticamente**. O nome não vai para banco, backup, auditoria, hash nem serviço externo.
4. Para baixar de novo, digita-se o nome outra vez. Sem nome, o marcador sai destacado em vermelho para preenchimento no Word.
5. Nunca escrever nome, CPF, telefone ou e-mail dentro das seções. CPF, e-mail e telefone são recusados automaticamente.
6. A guarda do documento final assinado e da correspondência código ↔ pessoa é responsabilidade da(o) profissional, **fora do sistema**, pelo prazo exigido pelo CFP.

Essa regra está no `CLAUDE.md` (regra 4) e aparece como instrução fixa na página **Documentos**.

## 8. Critérios de aceitação
| Critério | Situação |
|---|---|
| Cadastro persiste após reinício e suporta várias versões do mesmo instrumento | ✅ testado |
| Teste desfavorável, não verificado ou vencido não é liberado | ✅ testado |
| Toda alteração gera auditoria; histórico SATEPSI preservado | ✅ testado |
| Backup integral exportável e restaurável | ✅ testado (ida e volta idêntica, SQLite e PostgreSQL) |
| Resultados psicométricos reproduzem bases de referência | pós-MVP C |
| IA não cria valores numéricos e distingue cálculo de interpretação | ✅ números novos sinalizados; respostas rotuladas como sugestão |
| Documentos permanecem rascunho até aprovação | ✅ testado |
| Nenhum dado de identificação direta é coletado | regra de projeto (CLAUDE.md) |

## 9. Pendências
- Usuário: conferir no SATEPSI cada versão do inventário e registrar no sistema.
- Usuário: implantar seguindo `docs/IMPLANTACAO.md`.
- Técnica: restauração de backup.

## Referências
SATEPSI: <https://satepsi.cfp.org.br/> · CFP: <https://site.cfp.org.br/> · LGPD: Lei nº 13.709/2018 (consultar texto oficial atualizado).
