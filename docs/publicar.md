# Pôr o Rota no ar para o professor

O enunciado pede, no item 4(a), **link de acesso e credenciais**. Este
documento é o caminho testado para produzir esse link.

## A decisão de segurança que vem antes do link

A instância pública roda com **`ROTA_MODO=demo`**, que **recusa o login do
SIGAA** (HTTP 403) e tira o formulário de senha da tela.

Isso não é limitação do protótipo, é o desenho correto. Uma instância pública
do Rota com o login aberto seria, na prática, uma página num endereço
desconhecido pedindo a senha institucional de quem chegasse — e quem a
digitasse não teria como saber quem está do outro lado. O modo completo existe
quando o próprio aluno sobe o sistema na máquina dele, contra a API dele.

O professor não perde nada com isso: o modo demonstração carrega um aluno
fictício, montado sobre a matriz e a oferta reais do curso, e exercita **o fluxo inteiro** de apoio à decisão, que é o
que o enunciado pede avaliar ("podendo utilizar dados simulados, bases
reduzidas ou integrações mockadas").

**Credenciais a declarar no PDF:** nenhuma. Basta abrir o link e clicar em
*Entrar na demonstração*. Dizer isso explicitamente é melhor do que omitir.

---

## O artefato: uma imagem Docker

```bash
docker build -t rota .
docker run --rm -p 8012:8012 -e ROTA_MODO=demo rota
```

**Verificado em 03/11/2026**, da imagem recém-construída:

| checagem | resultado |
|---|---|
| `GET /api/status` | `{"rota":"ok","modo":"demo","so_demo":true,"sigaa_api":null}` |
| `POST /api/login` com credencial do SIGAA | **403**, com a explicação |
| `POST /api/login` demo | 200 |
| `POST /api/painel` | 200 · 11 pendências · fila SA 6 · agrupamento k=2 |
| fluxo na tela (login → caminhos → agrupamento) | renderiza |
| validador de usabilidade, 6 telas | **0 erros** |

A imagem não precisa de rede para fora: em `demo` ela **não fala com a
sigaa-ufba-api**, então não há dependência de o SIGAA estar no ar no dia da
avaliação. É a mesma razão pela qual o snapshot foi congelado.

---

## Onde hospedar

Qualquer host que aceite um Dockerfile e leia a variável `PORT` serve. Duas
opções gratuitas, sem cartão de crédito:

### Hugging Face Spaces (Docker)

1. Criar conta em <https://huggingface.co> e um **Space** do tipo *Docker*.
2. Subir este repositório no Space (ou apontar para o GitHub).
3. No `README.md` do Space, declarar a porta:
   ```yaml
   ---
   title: Rota
   sdk: docker
   app_port: 8012
   ---
   ```
4. Em *Settings → Variables*, criar `ROTA_MODO=demo`.

URL durável: `https://<usuario>-<space>.hf.space`.

### Render (Web Service · Docker)

1. Conta em <https://render.com>, *New → Web Service*, apontar para o
   repositório.
2. Ambiente **Docker**; Render injeta `PORT` sozinho.
3. Variável de ambiente `ROTA_MODO=demo`.

Atenção ao plano gratuito: o serviço **dorme** após inatividade e a primeira
visita leva ~50 s para responder. Se for o escolhido, **avisar isso no PDF**,
porque um professor que abre o link e vê uma página pendurada conclui que o
sistema não funciona.

### O que não serve

- **GitHub Pages / Netlify / Vercel estático** — o Rota tem servidor Python; a
  decisão mora nele, não no navegador.
- **Túnel temporário** (`trycloudflare`, `ngrok` grátis) — o endereço morre
  quando a máquina desliga ou o processo cai. Para um link que precisa
  responder dias depois da entrega, é a pior escolha: falha exatamente no
  momento em que ninguém está olhando.

---

## Antes de entregar o link

- [ ] abrir o link numa janela anônima e **clicar em Entrar na demonstração**
- [ ] conferir que o formulário de senha **não** aparece
- [ ] percorrer as seis telas
- [ ] imprimir o Relatório em PDF (é o botão que mais quebra em host novo)
- [ ] anotar no PDF do trabalho: endereço, "sem credenciais" e, se for Render,
      o aviso do primeiro acesso lento
