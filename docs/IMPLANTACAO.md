# Colocar o SIAP-IA no ar (sem instalar nada no Mac)

Arquitetura escolhida, porque o computador local é antigo:

```
Navegador (Mac, celular)  →  Streamlit Community Cloud (roda o app, grátis)
                                       │
                                       └→ Neon (banco PostgreSQL, grátis)  ← os dados ficam aqui
```

Por que dois serviços: o Streamlit Cloud **apaga arquivos locais** quando o app reinicia. Por isso o banco
precisa ficar fora dele. Sem `DATABASE_URL`, o app usa SQLite e serve só para teste.

> Planos gratuitos e telas dessas plataformas mudam com frequência. Se algum botão tiver outro nome, procure a opção equivalente.

## 1. Banco de dados (Neon) — ~5 min
1. Acesse <https://neon.tech> e entre com sua conta GitHub ou Google.
2. **Create project** → nome `siap-ia` → região **São Paulo (sa-east-1)**, se disponível; senão, a mais próxima.
3. Na tela do projeto, clique em **Connect** e copie a *connection string*
   (começa com `postgresql://` e termina com `?sslmode=require`).
4. Guarde essa linha: ela é a senha do seu banco. Não a envie por chat nem e-mail.

## 2. Aplicativo (Streamlit Community Cloud) — ~10 min
1. Acesse <https://share.streamlit.io> e entre com a **conta GitHub** dona do repositório `siap-ia`.
   Autorize o acesso a repositórios privados quando for solicitado.
2. **Create app** → opção de implantar a partir do GitHub.
   - Repository: `borgesfs-cmd/siap-ia` · Branch: `main` · Main file: `app.py`
   - App URL: escolha algo discreto.
3. **Advanced settings**:
   - Python: **3.12**
   - Secrets: cole o texto abaixo, com os seus valores:
     ```toml
     DATABASE_URL = "postgresql://...copiado do Neon...?sslmode=require"
     APP_PASSWORD = "uma frase longa só sua"
     ```
4. **Deploy**. A primeira subida leva alguns minutos. O inventário inicial é carregado automaticamente.
5. Depois de publicado: **Settings → Sharing** → deixe o app **privado** e convide só o seu e-mail.
   Ficam duas camadas de acesso: o login do Streamlit e a senha do app.

## 3. Uso no dia a dia
- O app "dorme" após um período sem uso. Ao abrir, clique em *Wake up* e aguarde alguns segundos. Os dados estão no Neon e não se perdem.
- Faça um **backup mensal** em *Auditoria e backup* e guarde o arquivo numa pasta protegida.
  No Mac: Utilitário de Disco → *Arquivo → Nova Imagem → Imagem de Pasta*, com criptografia AES-256.
- Atualizações enviadas ao GitHub (branch `main`) são publicadas automaticamente.

## 4. Privacidade (lembrete)
- Não cadastre nome, CPF ou contato de avaliandos: use códigos (`AV-2026-001`). A tabela que liga código à pessoa fica **fora** do sistema, sob sua guarda.
- Evidências do SATEPSI são capturas de páginas públicas e não contêm dados pessoais.
- Os planos gratuitos não oferecem contrato de tratamento de dados. Por isso, não use dados identificáveis.
