# -*- coding: utf-8 -*-
"""
Gera o dados.json do app a partir do banco do OM (so' leitura).
Roda no GitHub Actions. A senha do banco NAO fica aqui: vem dos "segredos"
do repositorio (OM_HOST, OM_PORT, OM_USER, OM_PASSWORD, OM_DATABASE).
"""
import json, os, re, sys, unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo
import mysql.connector as mc

LOJAS_APP = ['Bastos', 'Deposito', 'Iacri', 'Osvaldo Cruz', 'Parapua', 'Rinópolis', 'Tupa']  # nao mude: o celular identifica a loja por este nome
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def normaliza(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode('ascii')
    return s.upper().strip()


def main():
    faltando = [k for k in ('OM_HOST', 'OM_PORT', 'OM_USER', 'OM_PASSWORD', 'OM_DATABASE') if not os.environ.get(k)]
    if faltando:
        sys.exit('Faltam os segredos no GitHub: ' + ', '.join(faltando))
    print('Conectando no banco do OM...')
    conn = mc.connect(host=os.environ['OM_HOST'], port=int(os.environ['OM_PORT']), user=os.environ['OM_USER'],
                      password=os.environ['OM_PASSWORD'], database=os.environ['OM_DATABASE'], connection_timeout=30)
    cur = conn.cursor()
    print('Conectado.')

    cur.execute('SELECT cod_empresa, emp_nomefant FROM empresas')
    empresas = cur.fetchall()
    mapa = {}
    for nome in LOJAS_APP:
        achados = [cod for cod, nf in empresas if normaliza(nome) in normaliza(nf)]
        if len(achados) != 1:
            sys.exit(f"'{nome}' deu {len(achados)} resultado(s) em empresas. Abortando sem mexer no app.")
        mapa[nome] = achados[0]

    cur.execute('SELECT DISTINCT cod_grupo, grp_descricao FROM view_produtos WHERE grp_descricao IS NOT NULL ORDER BY grp_descricao')
    grupos_rows = cur.fetchall()
    grupos = [g[1] for g in grupos_rows]
    idx_grupo = {cod: i for i, (cod, _) in enumerate(grupos_rows)}
    idx_sem = len(grupos)
    grupos.append('SEM GRUPO')

    e = []
    for nome in LOJAS_APP:
        cur.execute("""SELECT cod_produto, prod_est_atual_fisico, COALESCE(prod_valor_venda, 0) FROM view_produtos
                       WHERE cod_empresa = %s AND (prod_inativo = 0 OR prod_inativo IS NULL)
                         AND (prod_cancelado = 0 OR prod_cancelado IS NULL)
                         AND prod_est_atual_fisico IS NOT NULL AND prod_est_atual_fisico <> 0""", (mapa[nome],))
        linhas = [[int(c), float(q), round(float(pr), 2)] for c, q, pr in cur.fetchall()]
        if not linhas:
            sys.exit(f"'{nome}' voltou com 0 produtos - parece erro. Abortando sem mexer no app.")
        e.append(linhas)
        print(f'  {nome}: {len(linhas)} produtos')

    cur.execute("""SELECT cod_produto, MAX(prod_cod_barra), MAX(prod_descricao), MAX(cod_grupo), MAX(prod_unidade), MAX(prod_valor_venda)
                   FROM view_produtos WHERE (prod_inativo = 0 OR prod_inativo IS NULL) GROUP BY cod_produto""")
    p = [[int(c), ean or '', d or '', idx_grupo.get(g, idx_sem), (u or '').strip(), round(float(pr or 0), 2)]
         for c, ean, d, g, u, pr in cur.fetchall()]
    conn.close()
    if len(p) < 5000:
        sys.exit(f"So' {len(p)} produtos no catalogo - parece pouco. Abortando sem mexer no app.")

    gerado = datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y às %H:%M')
    with open(os.path.join(RAIZ, 'dados.json'), 'w', encoding='utf-8') as f:
        json.dump({'gerado': gerado, 'grupos': grupos, 'lojas': LOJAS_APP, 'p': p, 'e': e}, f, ensure_ascii=False, separators=(',', ':'))
    print(f'{len(p)} produtos no catalogo. Gerado em {gerado}.')

    sw = os.path.join(RAIZ, 'sw.js')
    t = open(sw, encoding='utf-8').read()
    n = int(re.search(r'contagem-v(\d+)', t).group(1)) + 1
    open(sw, 'w', encoding='utf-8').write(re.sub(r'contagem-v\d+', f'contagem-v{n}', t))
    print(f'sw.js: versao do cache v{n}.')


main()
