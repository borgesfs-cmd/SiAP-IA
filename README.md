# SIAP-IA

**Sistema Inteligente de Avaliação Psicológica** — uso pessoal e não comercial.

Versão atual: **Etapas 1 e 2 do MVP**
- **Catálogo de testes:** cadastro, versões independentes (ex.: d2 e d2-R), busca e edição com histórico.
- **Monitor SATEPSI (modo assistido):** você consulta o [site oficial](https://satepsi.cfp.org.br/) e registra a situação com evidência; o sistema bloqueia uso profissional de tudo que não estiver favorável **e** dentro da validade (padrão 90 dias).
- **Auditoria e backup:** toda alteração é registrada; backup integral em JSON.

O inventário inicial (14 testes / 15 versões) entra como **não verificado**, portanto bloqueado.

> O sistema não armazena identificação direta de pessoas avaliadas e não substitui o julgamento profissional.

## Como usar
O sistema roda na nuvem e é acessado pelo navegador (não precisa instalar nada no Mac).
Siga **[docs/IMPLANTACAO.md](docs/IMPLANTACAO.md)** para colocá-lo no ar (≈20 minutos, gratuito).

## Desenvolvimento
```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
streamlit run app.py
```
O GitHub Actions roda os testes a cada envio. Regras do projeto para o Claude: [CLAUDE.md](CLAUDE.md).

## Documentos
- [Documento Mestre v1.1](docs/DOCUMENTO_MESTRE.md)
- [Histórico da conversa de planejamento](docs/HISTORICO_CONVERSA.md)
- [Guia de implantação](docs/IMPLANTACAO.md)

Referências: [SATEPSI](https://satepsi.cfp.org.br/) · [CFP](https://site.cfp.org.br/) · LGPD (Lei nº 13.709/2018).
