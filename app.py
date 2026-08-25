import streamlit as st
import sqlite3
import datetime
import pandas as pd
from io import BytesIO

# ==================== CONFIGURAÇÃO DA PÁGINA ====================
st.set_page_config(
    page_title="Controle de Bordados",
    page_icon="🧵",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==================== BANCO DE DADOS ====================
DB_NAME = "bordados.db"

def conectar_banco():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def criar_tabelas():
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT,
            email TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            empresa TEXT,
            numero_pedido TEXT,
            descricao_peca TEXT NOT NULL,
            tipo_bordado TEXT,
            quantidade INTEGER NOT NULL,
            data_entrada TEXT NOT NULL,
            prazo_entrega TEXT NOT NULL,
            data_saida TEXT,
            status TEXT NOT NULL,
            valor_total REAL,
            status_pagamento TEXT,
            observacoes TEXT,
            FOREIGN KEY (cliente_id) REFERENCES clientes (id)
        )
    """)
    # Garantir colunas existentes (para compatibilidade)
    cursor.execute("PRAGMA table_info(pedidos)")
    colunas = [info[1] for info in cursor.fetchall()]
    if "empresa" not in colunas:
        cursor.execute("ALTER TABLE pedidos ADD COLUMN empresa TEXT")
    if "numero_pedido" not in colunas:
        cursor.execute("ALTER TABLE pedidos ADD COLUMN numero_pedido TEXT")
    
    # Cliente padrão "CONFECÇÃO"
    cursor.execute("SELECT id FROM clientes WHERE nome = 'CONFECÇÃO'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO clientes (nome) VALUES ('CONFECÇÃO')")
    conn.commit()
    conn.close()

# Inicializa o banco ao carregar o app
criar_tabelas()

# ==================== FUNÇÕES AUXILIARES ====================
def data_atual():
    return datetime.date.today().strftime("%Y-%m-%d")

def formatar_data_br(data_str):
    if not data_str:
        return ""
    try:
        d = datetime.datetime.strptime(data_str, "%Y-%m-%d")
        return d.strftime("%d/%m/%Y")
    except:
        return data_str

def calcular_dias_entre(data1, data2):
    try:
        d1 = datetime.datetime.strptime(data1, "%Y-%m-%d")
        d2 = datetime.datetime.strptime(data2, "%Y-%m-%d")
        return (d1 - d2).days
    except:
        return None

# ==================== FUNÇÕES DE NEGÓCIO ====================
def listar_clientes():
    conn = conectar_banco()
    df = pd.read_sql("SELECT id, nome, telefone, email FROM clientes ORDER BY nome", conn)
    conn.close()
    return df

def salvar_cliente(nome, telefone, email):
    conn = conectar_banco()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO clientes (nome, telefone, email) VALUES (?, ?, ?)",
                       (nome, telefone, email))
        conn.commit()
        return True, f"Cliente '{nome}' cadastrado!"
    except sqlite3.Error as e:
        return False, f"Erro: {e}"
    finally:
        conn.close()

def atualizar_cliente(id, nome, telefone, email):
    conn = conectar_banco()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE clientes SET nome=?, telefone=?, email=? WHERE id=?",
                       (nome, telefone, email, id))
        conn.commit()
        return True, f"Cliente #{id} atualizado!"
    except sqlite3.Error as e:
        return False, f"Erro: {e}"
    finally:
        conn.close()

def excluir_cliente(id):
    conn = conectar_banco()
    cursor = conn.cursor()
    try:
        # Verifica se tem pedidos
        cursor.execute("SELECT COUNT(*) FROM pedidos WHERE cliente_id = ?", (id,))
        if cursor.fetchone()[0] > 0:
            return False, "Cliente possui pedidos vinculados. Exclua os pedidos primeiro."
        cursor.execute("DELETE FROM clientes WHERE id = ?", (id,))
        conn.commit()
        return True, f"Cliente #{id} excluído."
    except sqlite3.Error as e:
        return False, f"Erro: {e}"
    finally:
        conn.close()

# ---------- Pedidos ----------
def listar_pedidos(filtro_status=None):
    conn = conectar_banco()
    query = """
        SELECT p.id, p.numero_pedido, c.nome AS cliente, p.empresa, p.descricao_peca,
               p.quantidade, p.prazo_entrega, p.status, p.valor_total, p.status_pagamento,
               p.data_entrada, p.data_saida, p.observacoes, p.cliente_id, p.tipo_bordado
        FROM pedidos p
        JOIN clientes c ON p.cliente_id = c.id
    """
    params = []
    if filtro_status == "Atrasados":
        hoje = data_atual()
        query += " WHERE p.prazo_entrega < ? AND p.status != 'Entregue'"
        params.append(hoje)
    elif filtro_status and filtro_status != "Todos":
        status_map = {"Pendente": "Pendente", "Em Produção": "Em Producao",
                      "Concluído": "Concluido", "Entregue": "Entregue"}
        if filtro_status in status_map:
            query += " WHERE p.status = ?"
            params.append(status_map[filtro_status])
    query += " ORDER BY p.prazo_entrega ASC"
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df

def salvar_pedido(cliente_id, numero_pedido, empresa, descricao, tipo_bordado,
                  quantidade, prazo_entrega, valor_total, observacoes):
    conn = conectar_banco()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO pedidos
            (cliente_id, numero_pedido, empresa, descricao_peca, tipo_bordado,
             quantidade, data_entrada, prazo_entrega, status, valor_total,
             status_pagamento, observacoes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cliente_id, numero_pedido, empresa, descricao, tipo_bordado,
              quantidade, data_atual(), prazo_entrega, "Pendente",
              valor_total, "Pendente", observacoes))
        conn.commit()
        return True, "Pedido registrado com sucesso!"
    except sqlite3.Error as e:
        return False, f"Erro: {e}"
    finally:
        conn.close()

def atualizar_pedido(id, cliente_id, numero_pedido, empresa, descricao, tipo_bordado,
                     quantidade, prazo_entrega, valor_total, observacoes):
    conn = conectar_banco()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE pedidos SET
                cliente_id = ?, numero_pedido = ?, empresa = ?,
                descricao_peca = ?, tipo_bordado = ?, quantidade = ?,
                prazo_entrega = ?, valor_total = ?, observacoes = ?
            WHERE id = ?
        """, (cliente_id, numero_pedido, empresa, descricao, tipo_bordado,
              quantidade, prazo_entrega, valor_total, observacoes, id))
        conn.commit()
        return True, f"Pedido #{id} atualizado!"
    except sqlite3.Error as e:
        return False, f"Erro: {e}"
    finally:
        conn.close()

def excluir_pedido(id):
    conn = conectar_banco()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM pedidos WHERE id = ?", (id,))
        conn.commit()
        return True, f"Pedido #{id} excluído."
    except sqlite3.Error as e:
        return False, f"Erro: {e}"
    finally:
        conn.close()

def atualizar_status_pedido(id, novo_status, data_saida=None, pagamento=None):
    conn = conectar_banco()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE pedidos SET status = ?, data_saida = ? WHERE id = ?",
                       (novo_status, data_saida, id))
        if pagamento:
            cursor.execute("UPDATE pedidos SET status_pagamento = ? WHERE id = ?",
                           (pagamento, id))
        conn.commit()
        return True, f"Status atualizado para '{novo_status}'."
    except sqlite3.Error as e:
        return False, f"Erro: {e}"
    finally:
        conn.close()

# ---------- Importação Excel ----------
def importar_excel(df):
    conn = conectar_banco()
    cursor = conn.cursor()
    
    # Garantir cliente CONFEÇÃO
    cursor.execute("SELECT id FROM clientes WHERE nome = 'CONFECÇÃO'")
    cliente = cursor.fetchone()
    if not cliente:
        cursor.execute("INSERT INTO clientes (nome) VALUES ('CONFECÇÃO')")
        cliente_id = cursor.lastrowid
    else:
        cliente_id = cliente[0]
    conn.commit()
    
    inseridos = 0
    renomeados = 0
    erros = 0
    
    for idx, row in df.iterrows():
        try:
            data_entrada = pd.to_datetime(row["DATA TERCEIRIZAÇÃO"]).strftime("%Y-%m-%d")
            numero_pedido = str(row["PED"]).strip()
            empresa_nome = str(row["CLIENTE"]).strip().upper()
            qtd = int(row["QTD"])
            peca = str(row["PEÇA"]).strip()
            data_saida = pd.to_datetime(row["DATA SAIDA"]).strftime("%Y-%m-%d") if pd.notna(row["DATA SAIDA"]) else None
            
            # Renomeação de duplicatas
            cursor.execute("SELECT id FROM pedidos WHERE numero_pedido = ? AND data_entrada = ?", (numero_pedido, data_entrada))
            if cursor.fetchone():
                base = numero_pedido
                sufixo = 2
                while True:
                    novo_num = f"{base}/{sufixo}"
                    cursor.execute("SELECT id FROM pedidos WHERE numero_pedido = ? AND data_entrada = ?", (novo_num, data_entrada))
                    if not cursor.fetchone():
                        numero_pedido = novo_num
                        renomeados += 1
                        break
                    sufixo += 1
            
            status = "Entregue" if data_saida else "Pendente"
            if data_saida:
                prazo_entrega = data_saida
            else:
                dt_ent = datetime.datetime.strptime(data_entrada, "%Y-%m-%d")
                prazo_entrega = (dt_ent + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
            
            oficina = str(row.get("OFICINA", "")).strip() if "OFICINA" in df.columns else ""
            observacao = f"OFICINA: {oficina}" if oficina else ""
            
            cursor.execute("""
                INSERT INTO pedidos
                (cliente_id, numero_pedido, empresa, descricao_peca, quantidade,
                 data_entrada, prazo_entrega, data_saida, status,
                 valor_total, status_pagamento, observacoes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (cliente_id, numero_pedido, empresa_nome, peca, qtd,
                  data_entrada, prazo_entrega, data_saida, status,
                  0.0, "Pendente", observacao))
            conn.commit()
            inseridos += 1
        except Exception as e:
            erros += 1
            st.error(f"Erro na linha {idx+2}: {e}")
    
    conn.close()
    return inseridos, renomeados, erros

# ==================== INTERFACE STREAMLIT ====================
st.title("🧵 Controle de Bordados - Confecção")

# Inicializar estados de edição
if "editando_cliente" not in st.session_state:
    st.session_state.editando_cliente = None
if "editando_pedido" not in st.session_state:
    st.session_state.editando_pedido = None

# ==================== ABAS ====================
tab1, tab2, tab3 = st.tabs(["👥 Clientes", "📦 Pedidos", "📊 Relatório"])

# ------------------------------------------------------------
# TAB 1 – CLIENTES
# ------------------------------------------------------------
with tab1:
    col_esq, col_dir = st.columns([1, 2])
    
    with col_esq:
        st.subheader("Cadastrar / Editar")
        with st.form("form_cliente"):
            nome = st.text_input("Nome*", key="cli_nome")
            telefone = st.text_input("Telefone", key="cli_tel")
            email = st.text_input("E-mail", key="cli_email")
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submitted = st.form_submit_button("💾 Salvar", use_container_width=True)
            with col_btn2:
                if st.form_submit_button("🔄 Limpar", use_container_width=True):
                    st.session_state.cli_nome = ""
                    st.session_state.cli_tel = ""
                    st.session_state.cli_email = ""
                    st.session_state.editando_cliente = None
                    st.rerun()
            
            if submitted:
                if not nome.strip():
                    st.error("O nome é obrigatório.")
                else:
                    if st.session_state.editando_cliente:
                        ok, msg = atualizar_cliente(st.session_state.editando_cliente, nome.strip(), telefone.strip(), email.strip())
                    else:
                        ok, msg = salvar_cliente(nome.strip(), telefone.strip(), email.strip())
                    if ok:
                        st.success(msg)
                        st.session_state.editando_cliente = None
                        st.rerun()
                    else:
                        st.error(msg)
    
    with col_dir:
        st.subheader("Lista de Clientes")
        df_clientes = listar_clientes()
        if not df_clientes.empty:
            # Exibir com seleção para edição/exclusão
            st.dataframe(df_clientes, use_container_width=True, hide_index=True)
            
            col_a, col_b, col_c = st.columns([1, 1, 2])
            with col_a:
                ids_disponiveis = df_clientes["id"].tolist()
                id_selecionado = st.selectbox("Selecionar ID", ids_disponiveis, key="sel_cliente")
            with col_b:
                if st.button("✏️ Editar", use_container_width=True):
                    cliente = df_clientes[df_clientes["id"] == id_selecionado].iloc[0]
                    st.session_state.editando_cliente = id_selecionado
                    st.session_state.cli_nome = cliente["nome"]
                    st.session_state.cli_tel = cliente["telefone"] if cliente["telefone"] else ""
                    st.session_state.cli_email = cliente["email"] if cliente["email"] else ""
                    st.rerun()
            with col_c:
                if st.button("🗑️ Excluir", use_container_width=True):
                    if st.session_state.get("confirmar_excluir_cliente") == id_selecionado:
                        ok, msg = excluir_cliente(id_selecionado)
                        if ok:
                            st.success(msg)
                            st.session_state.confirmar_excluir_cliente = None
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.session_state.confirmar_excluir_cliente = id_selecionado
                        st.warning(f"Clique novamente para confirmar exclusão do ID {id_selecionado}")
        else:
            st.info("Nenhum cliente cadastrado.")

# ------------------------------------------------------------
# TAB 2 – PEDIDOS
# ------------------------------------------------------------
with tab2:
    # Filtro
    filtro = st.selectbox("Filtrar por status:", 
                          ["Todos", "Pendente", "Em Produção", "Concluído", "Entregue", "Atrasados"],
                          key="filtro_pedidos")
    
    df_pedidos = listar_pedidos(filtro)
    
    # Colunas para ações
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.subheader("Lista de Pedidos")
        if not df_pedidos.empty:
            # Preparar exibição com cores
            display_df = df_pedidos.copy()
            display_df["prazo_entrega"] = display_df["prazo_entrega"].apply(formatar_data_br)
            display_df["valor_total"] = display_df["valor_total"].apply(lambda x: f"R$ {x:.2f}" if pd.notna(x) else "R$ 0,00")
            # Renomear colunas para exibição
            display_df = display_df.rename(columns={
                "id": "ID", "numero_pedido": "Nº Pedido", "cliente": "Cliente",
                "empresa": "Empresa", "descricao_peca": "Peça", "quantidade": "Qtd",
                "prazo_entrega": "Prazo", "status": "Status", "valor_total": "Valor",
                "status_pagamento": "Pagamento"
            })
            cols_exibir = ["ID", "Nº Pedido", "Cliente", "Empresa", "Peça", "Qtd", "Prazo", "Status", "Valor", "Pagamento"]
            st.dataframe(display_df[cols_exibir], use_container_width=True, hide_index=True)
            
            # Seleção para ações
            ids_pedidos = df_pedidos["id"].tolist()
            pedido_selecionado = st.selectbox("Selecionar Pedido (ID)", ids_pedidos, key="sel_pedido")
            
            col_act1, col_act2, col_act3, col_act4 = st.columns(4)
            with col_act1:
                if st.button("✏️ Editar", use_container_width=True):
                    st.session_state.editando_pedido = pedido_selecionado
                    st.rerun()
            with col_act2:
                if st.button("🗑️ Excluir", use_container_width=True):
                    if st.session_state.get("confirmar_excluir_pedido") == pedido_selecionado:
                        ok, msg = excluir_pedido(pedido_selecionado)
                        if ok:
                            st.success(msg)
                            st.session_state.confirmar_excluir_pedido = None
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.session_state.confirmar_excluir_pedido = pedido_selecionado
                        st.warning(f"Clique novamente para confirmar exclusão do pedido {pedido_selecionado}")
            with col_act3:
                if st.button("🔄 Status", use_container_width=True):
                    st.session_state.mostrar_status_dialog = pedido_selecionado
                    st.rerun()
            with col_act4:
                if st.button("🔄 Atualizar Lista", use_container_width=True):
                    st.rerun()
        else:
            st.info("Nenhum pedido encontrado.")
    
    with col_right:
        st.subheader("📥 Novo Pedido")
        with st.expander("Clique para abrir o formulário", expanded=False):
            with st.form("form_pedido"):
                conn = conectar_banco()
                clientes_opts = pd.read_sql("SELECT id, nome FROM clientes ORDER BY nome", conn)
                conn.close()
                if clientes_opts.empty:
                    st.warning("Cadastre um cliente primeiro!")
                else:
                    cliente_id = st.selectbox("Cliente*", clientes_opts["id"].tolist(),
                                              format_func=lambda x: clientes_opts[clientes_opts["id"]==x]["nome"].iloc[0])
                    numero_ped = st.text_input("Nº Pedido (opcional)")
                    empresa = st.text_input("Empresa (opcional)")
                    descricao = st.text_input("Descrição da peça*")
                    tipo_bordado = st.text_input("Tipo de bordado")
                    qtd = st.number_input("Quantidade*", min_value=1, value=1, step=1)
                    vu = st.number_input("Valor unitário (R$)", min_value=0.0, value=0.0, step=0.10, format="%.2f")
                    valor_total = st.number_input("Valor total (R$)", min_value=0.0, value=qtd*vu, step=0.10, format="%.2f")
                    prazo = st.date_input("Prazo de entrega*", value=datetime.date.today() + datetime.timedelta(days=7))
                    observacoes = st.text_area("Observações", height=68)
                    
                    submitted_ped = st.form_submit_button("💾 Salvar Pedido")
                    if submitted_ped:
                        if not descricao.strip():
                            st.error("Descrição é obrigatória.")
                        elif cliente_id is None:
                            st.error("Selecione um cliente.")
                        else:
                            ok, msg = salvar_pedido(
                                cliente_id, numero_ped.strip(), empresa.strip(),
                                descricao.strip(), tipo_bordado.strip(), qtd,
                                prazo.strftime("%Y-%m-%d"), valor_total, observacoes.strip()
                            )
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)

    # ---------- DIÁLOGO DE STATUS (abre quando st.session_state.mostrar_status_dialog) ----------
    if st.session_state.get("mostrar_status_dialog"):
        pedido_id = st.session_state.mostrar_status_dialog
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM pedidos WHERE id = ?", (pedido_id,))
        res = cursor.fetchone()
        conn.close()
        if res:
            status_atual = res[0]
            st.divider()
            st.subheader(f"🔄 Atualizar Status - Pedido #{pedido_id}")
            st.write(f"**Status atual:** {status_atual}")
            
            with st.form("form_status"):
                novo_status = st.selectbox("Novo status:", ["Pendente", "Em Produção", "Concluído", "Entregue"])
                marcar_pago = st.checkbox("Marcar como pago (se for Entregue)")
                
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    if st.form_submit_button("✅ Atualizar", use_container_width=True):
                        status_map = {"Pendente": "Pendente", "Em Produção": "Em Producao",
                                      "Concluído": "Concluido", "Entregue": "Entregue"}
                        novo_status_db = status_map[novo_status]
                        data_saida = data_atual() if novo_status == "Entregue" else None
                        pagamento = "Pago" if (novo_status == "Entregue" and marcar_pago) else None
                        ok, msg = atualizar_status_pedido(pedido_id, novo_status_db, data_saida, pagamento)
                        if ok:
                            st.success(msg)
                            st.session_state.mostrar_status_dialog = None
                            st.rerun()
                        else:
                            st.error(msg)
                with col_s2:
                    if st.form_submit_button("❌ Fechar", use_container_width=True):
                        st.session_state.mostrar_status_dialog = None
                        st.rerun()

    # ---------- EDITAR PEDIDO (expanded) ----------
    if st.session_state.editando_pedido:
        pedido_id = st.session_state.editando_pedido
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cliente_id, numero_pedido, empresa, descricao_peca, tipo_bordado,
                   quantidade, prazo_entrega, valor_total, observacoes
            FROM pedidos WHERE id = ?
        """, (pedido_id,))
        dados = cursor.fetchone()
        conn.close()
        if dados:
            (cli_id, num_ped, empresa, desc, tipo, qtd, prazo, val_total, obs) = dados
            st.divider()
            st.subheader(f"✏️ Editar Pedido #{pedido_id}")
            
            conn2 = conectar_banco()
            clientes_opts2 = pd.read_sql("SELECT id, nome FROM clientes ORDER BY nome", conn2)
            conn2.close()
            
            with st.form("form_edit_pedido"):
                novo_cli = st.selectbox("Cliente*", clientes_opts2["id"].tolist(),
                                        format_func=lambda x: clientes_opts2[clientes_opts2["id"]==x]["nome"].iloc[0],
                                        index=clientes_opts2[clientes_opts2["id"]==cli_id].index[0] if cli_id in clientes_opts2["id"].values else 0)
                novo_num = st.text_input("Nº Pedido", value=num_ped if num_ped else "")
                novo_empresa = st.text_input("Empresa", value=empresa if empresa else "")
                novo_desc = st.text_input("Descrição da peça*", value=desc)
                novo_tipo = st.text_input("Tipo de bordado", value=tipo if tipo else "")
                novo_qtd = st.number_input("Quantidade*", min_value=1, value=qtd, step=1)
                novo_vu = st.number_input("Valor unitário (R$)", min_value=0.0, value=val_total/qtd if qtd>0 else 0.0, step=0.10, format="%.2f")
                novo_valor = st.number_input("Valor total (R$)", min_value=0.0, value=val_total, step=0.10, format="%.2f")
                novo_prazo = st.date_input("Prazo de entrega*", value=datetime.datetime.strptime(prazo, "%Y-%m-%d").date())
                novo_obs = st.text_area("Observações", value=obs if obs else "", height=68)
                
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                        if not novo_desc.strip():
                            st.error("Descrição é obrigatória.")
                        else:
                            ok, msg = atualizar_pedido(
                                pedido_id, novo_cli, novo_num.strip(), novo_empresa.strip(),
                                novo_desc.strip(), novo_tipo.strip(), novo_qtd,
                                novo_prazo.strftime("%Y-%m-%d"), novo_valor, novo_obs.strip()
                            )
                            if ok:
                                st.success(msg)
                                st.session_state.editando_pedido = None
                                st.rerun()
                            else:
                                st.error(msg)
                with col_e2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state.editando_pedido = None
                        st.rerun()

    # ---------- IMPORTAR EXCEL ----------
    st.divider()
    st.subheader("📤 Importar Planilha Excel")
    uploaded_file = st.file_uploader("Escolha um arquivo .xlsx ou .xls", type=["xlsx", "xls"])
    if uploaded_file is not None:
        try:
            df_import = pd.read_excel(uploaded_file)
            # Normalizar colunas
            df_import.columns = df_import.columns.str.strip().str.upper()
            colunas_necessarias = ["DATA TERCEIRIZAÇÃO", "PED", "CLIENTE", "QTD", "PEÇA", "DATA SAIDA"]
            if all(col in df_import.columns for col in colunas_necessarias):
                if st.button("📥 Confirmar Importação", use_container_width=True):
                    with st.spinner("Importando..."):
                        ins, ren, err = importar_excel(df_import)
                    st.success(f"✅ Inseridos: {ins}  |  🔄 Renomeados: {ren}  |  ❌ Erros: {err}")
                    st.rerun()
            else:
                st.error(f"Colunas obrigatórias: {', '.join(colunas_necessarias)}. Encontradas: {', '.join(df_import.columns)}")
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")

# ------------------------------------------------------------
# TAB 3 – RELATÓRIO
# ------------------------------------------------------------
with tab3:
    st.subheader("📊 Relatório Gerencial")
    
    if st.button("🔄 Atualizar Relatório", use_container_width=False):
        st.rerun()
    
    conn = conectar_banco()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM pedidos")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM pedidos WHERE status = 'Pendente'")
    pendentes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM pedidos WHERE status = 'Em Producao'")
    producao = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM pedidos WHERE status = 'Concluido'")
    concluidos = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM pedidos WHERE status = 'Entregue'")
    entregues = cursor.fetchone()[0]
    
    hoje = data_atual()
    cursor.execute("SELECT COUNT(*) FROM pedidos WHERE prazo_entrega < ? AND status != 'Entregue'", (hoje,))
    atrasados = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(valor_total) FROM pedidos WHERE status = 'Entregue'")
    faturamento = cursor.fetchone()[0] or 0.0
    cursor.execute("SELECT SUM(valor_total) FROM pedidos WHERE status = 'Entregue' AND status_pagamento = 'Pendente'")
    a_receber = cursor.fetchone()[0] or 0.0
    
    # Alertas de saída
    alertas = []
    cursor.execute("SELECT id, cliente_id, descricao_peca, data_saida FROM pedidos WHERE data_saida IS NOT NULL")
    saidas = cursor.fetchall()
    for p in saidas:
        dias = calcular_dias_entre(hoje, p[3])
        if dias is not None and dias > 10:
            cursor.execute("SELECT nome FROM clientes WHERE id = ?", (p[1],))
            nome_cliente = cursor.fetchone()[0] if cursor.rowcount else "?"
            alertas.append(f"Pedido #{p[0]} - {nome_cliente} - {p[2]} (saída há {dias} dias)")
    conn.close()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📦 Total de Pedidos", total)
    col1.metric("⏳ Pendentes", pendentes, delta="Atenção" if pendentes>0 else None)
    col2.metric("⚙️ Em Produção", producao)
    col2.metric("✅ Concluídos", concluidos)
    col3.metric("🚚 Entregues", entregues)
    col3.metric("🔴 Atrasados", atrasados, delta="Urgente" if atrasados>0 else None)
    
    st.divider()
    col_f1, col_f2 = st.columns(2)
    col_f1.metric("💰 Faturamento total", f"R$ {faturamento:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col_f2.metric("💳 A receber", f"R$ {a_receber:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    
    st.divider()
    if alertas:
        st.warning("⚠️ Pedidos com saída há mais de 10 dias:")
        for item in alertas:
            st.write(f"- {item}")
    else:
        st.success("✅ Nenhum pedido com saída há mais de 10 dias.")