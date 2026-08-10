
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from tkinter.filedialog import askopenfilename, asksaveasfilename
import tkinter.messagebox as messagebox
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.dates as mdates
import plotly.express as px
#from tksheet import Sheet
from datetime import datetime
from tkcalendar import DateEntry
import plotly.io as pio
import traceback
import inspect


pio.renderers.default="browser"


# -------------------------- Grupos ---------------------
groups = {
    "1. Parámetros Básicos": ["GLOBAL_Avg", "DIRECT_Avg", "DIFFUSE_Avg", "GH_CALC_Avg", "percent"],
    "2. Balance de onda corta": ["GLOBAL_Avg", "UPWARD_SW_Avg"],
    "3. Balance de onda larga": ["DOWNWARD_Avg", "UPWARD_LW_Avg", "DWIRTEMP_Avg", "UWIRTEMP_Avg", "CRPTemp_Avg"],
    "4. Meteorología": ["CRPTemp_Avg", "RELATIVE_HUMIDITY_Avg", "PRESSURE_Avg", "DEW_POINT_Avg"],
    "5. Ultravioleta": ["UVB_Avg", "UVTEMP_Avg", "UVSIGNAL_Avg"],
    "6. Dispersión": ["dif_GH_CALC_GLOBAL", "abs_dif_GH_CALC_GLOBAL", "pct_dif_GH_CALC_GLOBAL",
                      "ratio_GH_CALC_GLOBAL", "sum_SW"]
}


# ----------------Seleccion de datos-------------
def seleccion_datos():
    filename = askopenfilename(
        title="Selecciona un archivo CSV",
        filetypes=[("Archivos CSV", "*.csv")]
    )
    if not filename:
        return None
    return pd.read_csv(filename)


# ---------- limpieza de datos eliminando los -999.9 y -999.0------
def limpieza(df):
    return df.replace([-999.9, -999.0], np.nan)


# ----------------preprocesamiento de datos-------------
def preprocesamiento(df):
    df['TIMESTAMP'] = pd.to_datetime(df['TIMESTAMP'], dayfirst=True)

    numeric_cols = df.columns.drop('TIMESTAMP')
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')

    for col in ['CRPTemp_Avg', 'UVTEMP_Avg', 'DEW_POINT_Avg']:
        if col in df.columns:
            df[col] = df[col] + 273.15

    if set(['GH_CALC_Avg', 'GLOBAL_Avg']).issubset(df.columns):
        df['dif_GH_CALC_GLOBAL'] = df['GH_CALC_Avg'] - df['GLOBAL_Avg']
        df['ratio_GH_CALC_GLOBAL'] = df['GH_CALC_Avg'] / df['GLOBAL_Avg']
        df['abs_dif_GH_CALC_GLOBAL'] = abs(df['dif_GH_CALC_GLOBAL'])
        df['pct_dif_GH_CALC_GLOBAL'] = np.where(
            df['GLOBAL_Avg'] != 0,
            (df['dif_GH_CALC_GLOBAL'] / df['GLOBAL_Avg']) * 100,
            np.nan
        )

    if set(['DIFFUSE_Avg', 'DIRECT_Avg', 'ZenDeg']).issubset(df.columns):
        df['sum_SW'] = df['DIFFUSE_Avg'] + df['DIRECT_Avg'] * np.cos(np.radians(df['ZenDeg']))
        df['percent'] = 0.01 * df['sum_SW']

    return df


# -------------------------- Query State --------------------------
class QueryState:
    def __init__(self, name):
        self.name = name
        self.group = "1. Parámetros Básicos"
        self.variables = []
        self.fecha_inicio = None
        self.fecha_fin = None
        self.hora_ini = "00"
        self.min_ini = "00"
        self.hora_fin = "23"
        self.min_fin = "59"
        self.df_filtrado = None
        self.df_tabla=None


# -------------------------- Dashboard App --------------------------
class DashboardApp:
    def __init__(self, root):
        self.root = root

        self.df = None
        self.df_filtrado = None

        self.queries = []
        self.current_query = None
        
        self.hover_point = {}
        self.hover_annot = {}
        self.vars_sel = []

        self.block_hover = False
        self.df_tabla = None
        self.lines = []

        self.root.protocol("WM_DELETE_WINDOW",self.on_close_app)
        self.is_closing = False

    # -------- Layout Frames --------
        self.top_tabs = ctk.CTkFrame(root, height=55, corner_radius=15)
        self.top_tabs.pack(side="top", fill="x", padx=10, pady=(10, 5))

        self.body = ctk.CTkFrame(root, fg_color="transparent")
        self.body.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))

        self.sidebar = ctk.CTkFrame(self.body, width=320, corner_radius=15)
        self.sidebar.pack(side="left", fill="y", padx=(0, 10), pady=0)

        self.main = ctk.CTkFrame(self.body, corner_radius=15)
        self.main.pack(side="left", fill="both", expand=True, padx=0, pady=0)
        # Build UI
        self.build_tab_bar()
        self.build_sidebar()
        self.build_main()
        
        # Create first query
        self.nueva_consulta()

    # ---------------- Sidebar UI ----------------
    def build_sidebar(self):
        ctk.CTkLabel(self.sidebar, text="BSRN_igf",
                 font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15, 10))

    # ---- Scrollable content ----
        self.sidebar_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.sidebar_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        ctk.CTkButton(self.sidebar_scroll, text="Cargar CSV", command=self.cargar_csv)\
            .pack(padx=5, pady=5, fill="x")

    # Group option menu
        self.combo = ctk.CTkOptionMenu(self.sidebar_scroll,values=list(groups.keys()),
                                       command=self.actualizar_variables)
        self.combo.set("1. Parámetros Básicos")
        self.combo.pack(padx=5, pady=10, fill="x")

    # Variables section
        ctk.CTkLabel(self.sidebar_scroll, text="Variables",
                 font=ctk.CTkFont(size=14, weight="bold"))\
                    .pack(anchor="w", padx=5, pady=(10, 0))

        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(self.sidebar_scroll,
        placeholder_text="Buscar variable...",textvariable=self.search_var)
        self.search_entry.pack(padx=5, pady=(5, 5), fill="x")
        self.search_entry.bind("<KeyRelease>", lambda e: self.filtrar_variables())

        # --- Botones Variables (vertical) ---
        btn_frame = ctk.CTkFrame(self.sidebar_scroll, fg_color="transparent")
        btn_frame.pack(padx=5, pady=(0, 5), fill="x")

        ctk.CTkButton(
            btn_frame,
            text="Seleccionar todo",
            command=self.select_all_vars
            ).pack(fill="x", pady=(0, 5))

        ctk.CTkButton(
            btn_frame,
            text="Limpiar",
            fg_color="gray30",
            hover_color="gray40",
            command=self.clear_vars
            ).pack(fill="x")

        self.vars_scroll = ctk.CTkScrollableFrame(self.sidebar_scroll, height=150)
        self.vars_scroll.pack(padx=5, pady=5, fill="both")

        self.var_checks = {}
        self.current_vars = []

    # ---- Date filter ----
        ctk.CTkLabel(self.sidebar_scroll, text="Fecha inicio").pack(anchor="w", padx=5, pady=(10, 0))
        frame_ini = ctk.CTkFrame(self.sidebar_scroll, fg_color="transparent")
        frame_ini.pack(anchor="w", padx=5)

        self.fecha_inicio = DateEntry(frame_ini, width=12)
        self.fecha_inicio.pack(side=tk.LEFT)

        self.hora_ini = tk.Spinbox(frame_ini, from_=0, to=23, width=3, format="%02.0f",
                               command=self.previsualizar)
        self.min_ini = tk.Spinbox(frame_ini, from_=0, to=59, width=3, format="%02.0f",
                              command=self.previsualizar)

        self.hora_ini.pack(side=tk.LEFT, padx=2)
        self.min_ini.pack(side=tk.LEFT)

        ctk.CTkLabel(self.sidebar_scroll, text="Fecha fin").pack(anchor="w", padx=5, pady=(10, 0))
        frame_fin = ctk.CTkFrame(self.sidebar_scroll, fg_color="transparent")
        frame_fin.pack(anchor="w", padx=5)

        self.fecha_fin = DateEntry(frame_fin, width=12)
        self.fecha_fin.pack(side=tk.LEFT)

        self.hora_fin = tk.Spinbox(frame_fin, from_=0, to=23, width=3, format="%02.0f",
                               command=self.previsualizar)
        self.min_fin = tk.Spinbox(frame_fin, from_=0, to=59, width=3, format="%02.0f",
                              command=self.previsualizar)

        self.hora_fin.pack(side=tk.LEFT, padx=2)
        self.min_fin.pack(side=tk.LEFT)

    # ---- Fixed bottom actions (always visible) ----
        bottom_actions = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_actions.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(bottom_actions, text="Consultar tabla", command=self.consultar_tabla)\
            .pack(fill="x", pady=5)

        ctk.CTkButton(bottom_actions, text="Graficar", command=self.grafica_plotly)\
            .pack(fill="x", pady=5)

        ctk.CTkButton(bottom_actions, text="Exportar CSV", command=self.exportar_csv)\
            .pack(fill="x", pady=5)


    # ---------------- Main UI ----------------  
    def build_main(self):

    # ---------------- Top Bar ----------------
        top_bar = ctk.CTkFrame(
            self.main,
            fg_color="transparent"
    )

        top_bar.pack(
            fill="x",
            padx=15,
            pady=(10, 5)
        )

        self.status_label = ctk.CTkLabel(
            top_bar,
            text="Ready",
            text_color="gray"
        )

        self.status_label.pack(side="left")

        self.dark_switch = ctk.CTkSwitch(
            top_bar,
            text="Dark Mode",
            command=self.toggle_dark
        )

        self.dark_switch.pack(side="right")

    # ---------------- Content Area ----------------
        content_frame = ctk.CTkFrame(self.main)

        content_frame.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=(0, 10)
        )

    # GRID SOLO AQUÍ
        content_frame.grid_rowconfigure(0, weight=8)   #GRAFICA
        content_frame.grid_rowconfigure(1, weight=0)    #TOOLBAR
        content_frame.grid_rowconfigure(2, weight=5)    #TABLA
        content_frame.grid_columnconfigure(0, weight=1) 


    # ---------------- Plot Frame ----------------
        frame_plot = ctk.CTkFrame(content_frame)

        frame_plot.grid(
            row=0,
            column=0,
            sticky="nsew",
            pady=(0, 5)
        )

        self.fig, self.ax = plt.subplots(figsize=(12, 5))

        self.canvas = FigureCanvasTkAgg(
            self.fig,
            master=frame_plot
        )

        self.canvas.draw()

        self.canvas.get_tk_widget().pack(
            fill="both",
            expand=True,
            padx=10,
            pady=10
        )

        self.canvas.mpl_connect(
            "motion_notify_event",
            self.on_hover
        )

    # Toolbar matplotlib oculta
        toolbar_frame = ctk.CTkFrame(content_frame)

        toolbar_frame.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(0,5)
        )

        self.mpl_toolbar = NavigationToolbar2Tk(
            self.canvas,
            toolbar_frame
        )

        self.mpl_toolbar.update()

        btn_max = tk.Button(
            self.mpl_toolbar,
            text="⛶ Maximizar",
            command=self.maximizar_grafica
        )

        btn_max.pack(side=tk.LEFT, padx=5)

    # ---------------- Table Frame ----------------
        self.table_frame = ctk.CTkFrame(content_frame)

        self.table_frame.grid(
            row=2,
            column=0,
            sticky="nsew"
        )
        self.table_frame.grid_rowconfigure(0, weight=1)
        self.table_frame.grid_rowconfigure(1, weight=0)
        self.table_frame.grid_columnconfigure(0, weight=1)

        tree_frame = ctk.CTkFrame(self.table_frame)
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(tree_frame,show="headings")

        scroll_y = ttk.Scrollbar(tree_frame,orient="vertical",command=self.tree.yview)
        

        self.tree.configure(yscrollcommand=scroll_y.set)

        self.tree.pack(side="left",fill="both",expand=True)
        scroll_y.pack(side="right",fill="y")
        
        # ---------- Paginación ----------

        self.page_size = 100
        self.current_page = 0

        self.page_frame = ctk.CTkFrame(self.table_frame,fg_color="transparent")

        self.page_frame.grid(row=1,column=0,sticky="ew",pady=(5,5))

        self.btn_prev = ctk.CTkButton(
        self.page_frame,
        text="← Anterior",
        width=110,
        command=self.pagina_anterior
        )

        self.btn_prev.pack(side="left",padx=20)

        self.lbl_pagina = ctk.CTkLabel(self.page_frame,text="Página 1 de 1")

        self.lbl_pagina.pack(side="left",expand=True)

        self.btn_next = ctk.CTkButton(self.page_frame,
            text="Siguiente →",width=110,command=self.pagina_siguiente)

        self.btn_next.pack(
        side="right",
        padx=20
        )


    def build_tab_bar(self):
        left = ctk.CTkFrame(self.top_tabs, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=10, pady=8)

        self.tabs_scroll = ctk.CTkScrollableFrame(left, height=40, orientation="horizontal")
        self.tabs_scroll.pack(side="left", fill="x", expand=True)

        right = ctk.CTkFrame(self.top_tabs, fg_color="transparent")
        right.pack(side="right", padx=10, pady=8)

        ctk.CTkButton(right,text="+ Nueva",width=90,
                      command=self.nueva_consulta).pack(side="right", padx=5)

        ctk.CTkButton(right, text="Renombrar", width=110,
                      command=self.renombrar_consulta_actual).pack(side="right", padx=5)

        ctk.CTkButton(right,text="Eliminar",width=90,fg_color="#8B0000",
                      hover_color="#A00000",
                      command=self.eliminar_consulta).pack(side="right", padx=5)

    # ---------------- Queries Logic ----------------
    def nueva_consulta(self):
        if self.current_query is not None:
            self.guardar_estado_actual()

        name = f"Consulta {len(self.queries) + 1}"
        q = QueryState(name)
        self.queries.append(q)
        self.current_query = q

        self.refresh_query_list()
        self.cargar_estado_query()

    def eliminar_consulta(self):
        if self.current_query is None:
            return

        if len(self.queries) == 1:
            messagebox.showwarning("Aviso", "No puedes eliminar la última consulta.")
            return

        self.queries.remove(self.current_query)
        self.current_query = self.queries[-1]

        self.refresh_query_list()
        self.cargar_estado_query()

    def refresh_query_list(self):
        for widget in self.tabs_scroll.winfo_children():
            widget.destroy()

        print("\n----- CONSULTAS -----")

        for q in self.queries:
            print(q.name,"ACTIVA" if q == self.current_query else "",q.variables)

            print("---------------------\n")

        for q in self.queries:
            is_active = (q == self.current_query)

            tab_frame = ctk.CTkFrame(self.tabs_scroll,corner_radius=12,
                                     fg_color="gray30" if is_active else "transparent")
            tab_frame.pack(side="left", padx=5, pady=5)

            btn_tab = ctk.CTkButton(
             tab_frame,
            text=q.name,
            fg_color="transparent",
            hover_color="gray40",
            command=lambda query=q: self.select_query(query),
            width=130
            )
            btn_tab.pack(side="left", padx=(5, 0), pady=3)

            btn_close = ctk.CTkButton(tab_frame,text="✖",width=30,fg_color="transparent",
                                      hover_color="#8B0000",command=lambda query=q: self.cerrar_consulta(query))
            btn_close.pack(side="left", padx=(2, 5), pady=3)

    def cerrar_consulta(self, query):
        if len(self.queries) == 1:
            messagebox.showwarning("Aviso", "No puedes cerrar la última consulta.")
            return

        if query == self.current_query:
            idx = self.queries.index(query)
            self.queries.remove(query)

            if idx > 0:
                self.current_query = self.queries[idx - 1]
            else:
                self.current_query = self.queries[0]

            self.cargar_estado_query()
        else:
            self.queries.remove(query)

        self.refresh_query_list()

    def renombrar_consulta_actual(self):
        if self.current_query is None:
            return

        dialog = ctk.CTkInputDialog(
            text="Nuevo nombre para la consulta:",
            title="Renombrar consulta"
        )

        nuevo = dialog.get_input()

        if nuevo is None:
            return

        nuevo = nuevo.strip()

        if nuevo == "":
            messagebox.showwarning("Aviso", "El nombre no puede estar vacío.")
            return

        self.current_query.name = nuevo
        self.refresh_query_list()    

    def select_query(self, query):
        print("Cambiando a:",query.name)
        self.block_hover =True
        self.guardar_estado_actual()
        self.current_query = query

        self.ax.clear()
        self.apply_plot_theme()
        self.canvas.draw_idle()

        self.cargar_estado_query()
        self.refresh_query_list()

        print("Cargando:",query.name)
        self.root.after(500,lambda:setattr(self,"block_hover",False))

    def guardar_estado_actual(self):
        q = self.current_query
        if q is None:
            return

        q.group = self.combo.get()
        q.variables = self.get_selected_vars()
        q.fecha_inicio = self.fecha_inicio.get_date()
        q.fecha_fin = self.fecha_fin.get_date()
        q.hora_ini = self.hora_ini.get()
        q.min_ini = self.min_ini.get()
        q.hora_fin = self.hora_fin.get()
        q.min_fin = self.min_fin.get()
        
        q.df_filtrado = self.df_filtrado
        q.df_tabla = getattr(self,"df_tabla",None)

        if q.df_filtrado is not None:
            print("Guardando DF",q.name,q.df_filtrado.shape)

        print("Guardando:",q.name,"vars=",q.variables,"grupo=",q.group)

    def cargar_estado_query(self):
        q = self.current_query
        if q is None:
            return
        self.hover_point.clear()
        self.hover_annot.clear()
        print( "Cargando:",q.name,q.variables,q.df_tabla is not None)
        
        self.combo.set(q.group)
        self.actualizar_variables(None)

        for v in q.variables:
            if v in self.var_checks:
                self.var_checks[v].set(True)

        if q.fecha_inicio:
            self.fecha_inicio.set_date(q.fecha_inicio)
        if q.fecha_fin:
            self.fecha_fin.set_date(q.fecha_fin)

        self.hora_ini.delete(0, tk.END)
        self.hora_ini.insert(0, q.hora_ini)

        self.min_ini.delete(0, tk.END)
        self.min_ini.insert(0, q.min_ini)

        self.hora_fin.delete(0, tk.END)
        self.hora_fin.insert(0, q.hora_fin)

        self.min_fin.delete(0, tk.END)
        self.min_fin.insert(0, q.min_fin)
        
        self.df_filtrado = q.df_filtrado
        if self.df_filtrado is not None:
            print("Recuperado DF:",q.name,self.df_filtrado.shape)
        self.df_tabla = q.df_tabla
        
        for item in self.tree.get_children():
            self.tree.delete(item)

    # ---------------- Restaurar tabla ----------------
        if q.df_tabla is not None:
            cols = list(q.df_tabla.columns)

            self.tree["columns"] = cols

            for col in cols:
                self.tree.heading(col, text=col)
                self.tree.column(col, width=140)

            self.df_tabla = q.df_tabla.copy()

            self.current_page = 0

            self.mostrar_pagina()
    # ---------------- Restaurar gráfica ----------------
        if q.df_filtrado is not None:
            print("Restaurando grafica:",q.name,q.df_filtrado.shape)

            self.root.after(100, self.previsualizar)

        else:

            self.ax.clear()
            self.apply_plot_theme()
            self.canvas.draw_idle()
    # ---------------- Variables UI ----------------
    def actualizar_variables(self, value=None):
        grupo = self.combo.get()
        vars_grupo = groups.get(grupo, [])

        self.current_vars = vars_grupo

        for widget in self.vars_scroll.winfo_children():
            widget.destroy()

        self.var_checks.clear()

        for v in vars_grupo:
            state = tk.BooleanVar(value=False)
            chk = ctk.CTkCheckBox(
                self.vars_scroll,
                text=v,
                variable=state,
                command=self.previsualizar
            )
            chk.pack(anchor="w", padx=10, pady=2)
            self.var_checks[v] = state

    def get_selected_vars(self):
        return [v for v, state in self.var_checks.items() if state.get()]

    def select_all_vars(self):
        for v in self.var_checks:
            self.var_checks[v].set(True)
        self.previsualizar()

    def clear_vars(self):
        for v in self.var_checks:
            self.var_checks[v].set(False)
        self.previsualizar()

    def filtrar_variables(self):
        texto = self.search_var.get().lower().strip()

        for widget in self.vars_scroll.winfo_children():
            widget.destroy()

        for v in self.current_vars:
            if texto in v.lower():
                chk = ctk.CTkCheckBox(
                    self.vars_scroll,
                    text=v,
                    variable=self.var_checks[v],
                    command=self.previsualizar
                )
                chk.pack(anchor="w", padx=10, pady=2)

    # ---------------- Dark Mode ----------------
    def toggle_dark(self):
        if self.dark_switch.get() == 1:
            ctk.set_appearance_mode("dark")
        else:
            ctk.set_appearance_mode("light")

        if self.df_filtrado is not None:
            self.previsualizar()
        else:
            self.apply_plot_theme()
            self.canvas.draw_idle()

    def apply_plot_theme(self):
        dark = (self.dark_switch.get() == 1)

        if dark:
            fig_bg = "#1e1e1e"
            ax_bg = "#1e1e1e"
            text_color = "white"
            grid_color = "#333333"
        else:
            fig_bg = "white"
            ax_bg = "white"
            text_color = "black"
            grid_color = "#dddddd"

        self.fig.patch.set_facecolor(fig_bg)
        self.ax.set_facecolor(ax_bg)

        self.ax.tick_params(colors=text_color)

        for spine in self.ax.spines.values():
            spine.set_color(text_color)

        self.ax.grid(True, color=grid_color)

        # Legend fix
        legend = self.ax.get_legend()
        if legend is not None:
            if dark:
                legend.get_frame().set_facecolor("#2b2b2b")
                legend.get_frame().set_edgecolor("#444444")
                for text in legend.get_texts():
                    text.set_color("white")
            else:
                legend.get_frame().set_facecolor("white")
                legend.get_frame().set_edgecolor("#cccccc")
                for text in legend.get_texts():
                    text.set_color("black")

        for v, annot in self.hover_annot.items():
            if dark:
                annot.get_bbox_patch().set_facecolor("#2b2b2b")
                annot.get_bbox_patch().set_edgecolor("#ffffff")
                annot.set_color("white")
            else:   
                annot.get_bbox_patch().set_facecolor("white")
                annot.get_bbox_patch().set_edgecolor("black")
                annot.set_color("black")


    def apply_table_theme(self):
        pass
    # ---------------- Main Functions ----------------
    def cargar_csv(self):
        df = seleccion_datos()
        if df is None:
            return

        self.df = preprocesamiento(limpieza(df))

        # Auto-set dates
        min_date = self.df["TIMESTAMP"].min()
        max_date = self.df["TIMESTAMP"].max()

        self.fecha_inicio.set_date(min_date.date())
        self.fecha_fin.set_date(max_date.date())

        messagebox.showinfo("OK", "Datos cargados correctamente")

    def obtener_filtro(self):
        if self.df is None:
            return None

        inicio = datetime(
            self.fecha_inicio.get_date().year,
            self.fecha_inicio.get_date().month,
            self.fecha_inicio.get_date().day,
            int(self.hora_ini.get()),
            int(self.min_ini.get()),
            0
        )

        fin = datetime(
            self.fecha_fin.get_date().year,
            self.fecha_fin.get_date().month,
            self.fecha_fin.get_date().day,
            int(self.hora_fin.get()),
            int(self.min_fin.get()),
            59
        )

        if fin < inicio:
            messagebox.showerror("Error", "La fecha fin no puede ser menor")
            return None

        return self.df.loc[
            (self.df["TIMESTAMP"] >= inicio) &
            (self.df["TIMESTAMP"] <= fin)
        ].copy()

    def previsualizar(self):

        print("previsualizar",self.current_query.name,inspect.stack()[1].function)

        if self.df is None:
            return

        self.vars_sel = self.get_selected_vars()

        if not self.vars_sel:
            self.ax.clear()
            self.apply_plot_theme()
            self.canvas.draw_idle()
            return

        df_f = self.obtener_filtro()
        if df_f is None or df_f.empty:
            return

        self.df_filtrado = df_f[["TIMESTAMP"]+self.vars_sel].copy()

        print("[PREVIEW]",self.current_query.name,"shape=", 
              self.df_filtrado.shape,"vars=", self.vars_sel)

        self.ax.clear()
        self.apply_plot_theme()
        
        for a in self.hover_annot.values():
            a.set_visible(False)

        self.hover_point.clear()
        self.hover_annot.clear()
        
 
        for v in self.vars_sel:
            if v not in self.df_filtrado.columns:
                continue                

            print(f"[PLOT] {v} existe={v in self.df_filtrado.columns}")

            line, =self.ax.plot(self.df_filtrado["TIMESTAMP"],self.df_filtrado[v],label=v)
            color = line.get_color()

            point, = self.ax.plot([], [], "o", color=color, markersize=7, zorder=10)
            annot = self.ax.annotate(
                "",
                xy=(0, 0),
                xytext=(15, 15),
                textcoords="offset points",
                bbox=dict(boxstyle="round", fc="white", ec="black"),
                arrowprops=dict(arrowstyle="->")
            )
            annot.set_visible(False)

            self.hover_point[v] = point
            self.hover_annot[v] = annot

       
        self.ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), fontsize=9)  

        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m-%Y'))
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())

        self.fig.autofmt_xdate()
        self.fig.tight_layout()

        self.canvas.draw_idle()

        self.guardar_estado_actual()

    
    def maximizar_grafica(self):
        
        vars_sel = self.get_selected_vars()
        
        if self.df_filtrado is None or not vars_sel:
            messagebox.showwarning(
            "Aviso",
            "No hay gráfica para mostrar"
        )
            return

        ventana = ctk.CTkToplevel(self.root)
        ventana.title("Gráfica ampliada")

        ventana.geometry("1600x900")
        ventana.state("zoomed")  # Windows

        fig, ax = plt.subplots(figsize=(16, 8))

        for v in vars_sel:
            if v in self.df_filtrado.columns:
                ax.plot(
                self.df_filtrado["TIMESTAMP"],
                self.df_filtrado[v],
                label=v
            )
        # Hover independiente ventana maximizada
        hover_annot = ax.annotate(
        "",
        xy=(0, 0),
        xytext=(15, 15),
        textcoords="offset points",
        bbox=dict(
            boxstyle="round",
            fc="white",
            ec="black"
        ),
        arrowprops=dict(
            arrowstyle="->"
        )
        )

        hover_annot.set_visible(False)

        hover_point, = ax.plot(
        [],
        [],
        "o",
        markersize=8,
        zorder=20
        )

        hover_point.set_visible(False)

        last_idx = None

        ax.legend()

        ax.xaxis.set_major_formatter(
        mdates.DateFormatter('%d-%m-%Y')
        )

        fig.autofmt_xdate()

        canvas = FigureCanvasTkAgg(fig, master=ventana)
        canvas.draw()

        canvas.get_tk_widget().pack(
        fill="both",
        expand=True
        )

        toolbar = NavigationToolbar2Tk(
        canvas,
        ventana
        )

        toolbar.update()

        fechas_num = mdates.date2num(
        self.df_filtrado["TIMESTAMP"]
        )        
        def on_hover_max(event):

            nonlocal last_idx

            if event.inaxes != ax:

                hover_annot.set_visible(False)
                hover_point.set_visible(False)

                canvas.draw_idle()

                return

            if event.xdata is None:
                return

            idx = np.abs(
            fechas_num - event.xdata
            ).argmin()

            if idx == last_idx:
                return

            last_idx = idx

            x = self.df_filtrado["TIMESTAMP"].iloc[idx]

            texto = x.strftime(
            "%Y-%m-%d %H:%M"
            )

            texto += "\n\n"

            for v in vars_sel:

                if v not in self.df_filtrado.columns:
                    continue

                try:

                    y_val = self.df_filtrado[v].iloc[idx]

                    texto += (
                     f"{v}: {y_val:.2f}\n"
                        )

                except:
                    pass

            y_ref = self.df_filtrado[
                vars_sel[0]
             ].iloc[idx]

            hover_point.set_data(
             [x],
                [y_ref]
             )

            hover_point.set_visible(True)

            hover_annot.xy = (
            x,
            y_ref
            )

            hover_annot.set_text(texto)

            hover_annot.set_visible(True)

            canvas.draw_idle()
        canvas.mpl_connect(
            "motion_notify_event",
            on_hover_max
        )    


    def consultar_tabla(self):
        if self.df is None:
            messagebox.showwarning("Aviso", "No hay datos cargados")
            return

        vars_sel = self.get_selected_vars()
        if not vars_sel:
            messagebox.showwarning("Aviso", "Selecciona al menos una variable")
            return

        df_f = self.obtener_filtro()
        if df_f is None or df_f.empty:
            messagebox.showwarning("Aviso", "No hay datos para mostrar")
            return

        self.df_filtrado = df_f[["TIMESTAMP"] + vars_sel].copy()

        for item in self.tree.get_children():
            self.tree.delete(item)

        cols = list(self.df_filtrado.columns)

        self.tree["columns"] = cols

        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=140)

        self.df_tabla = self.df_filtrado.copy()

        self.current_page = 0

        self.mostrar_pagina()

        self.df_tabla = self.df_filtrado.copy()
        self.current_query.df_tabla = self.df_tabla
        print("Tabla guardada",self.current_query.name,self.df_tabla.shape)
        self.guardar_estado_actual()

    def mostrar_pagina(self):
            if self.df_tabla is None:
                return

            if len(self.df_tabla) == 0:
                return

            if self.df_tabla is None:
                return

            for item in self.tree.get_children():
                self.tree.delete(item)

            inicio = self.current_page * self.page_size
            fin = inicio + self.page_size

            datos = self.df_tabla.iloc[inicio:fin]

            for row in datos.itertuples(index=False):
                self.tree.insert("", "end", values=row)

            total_paginas = max(1,(len(self.df_tabla) + self.page_size - 1) // self.page_size)

            self.lbl_pagina.configure(
                text=f"Página {self.current_page+1} de {total_paginas}")

            self.btn_prev.configure(
            state="normal" if self.current_page > 0 else "disabled")

            self.btn_next.configure(state="normal" if self.current_page < total_paginas-1 else "disabled")


    def pagina_siguiente(self):
        total_paginas = (len(self.df_tabla) + self.page_size - 1) // self.page_size

        if self.current_page < total_paginas-1:
            self.current_page += 1
            self.mostrar_pagina()


    def pagina_anterior(self):

        if self.current_page > 0:
            self.current_page -= 1
            self.mostrar_pagina()


    def grafica_plotly(self):
        if self.df is None:
            messagebox.showwarning("Aviso", "No hay datos cargados")
            return

        vars_sel = self.get_selected_vars()
        if not vars_sel:
            messagebox.showwarning("Aviso", "Selecciona al menos una variable")
            return

        df_f = self.obtener_filtro()
        if df_f is None or df_f.empty:
            messagebox.showwarning("Aviso", "No hay datos en ese rango")
            return

        df_plot = df_f[["TIMESTAMP"] + vars_sel].copy()

        fig = px.line(df_plot, x="TIMESTAMP", y=vars_sel, title="Gráfica Plotly")
        fig.show()

    def exportar_csv(self):
        if self.df is None:
            messagebox.showwarning("Aviso", "No hay datos cargados")
            return

        vars_sel = self.get_selected_vars()
        if not vars_sel:
            messagebox.showwarning("Aviso", "Selecciona al menos una variable")
            return

        df_f = self.obtener_filtro()
        if df_f is None or df_f.empty:
            messagebox.showwarning("Aviso", "No hay datos para exportar")
            return

        df_export = df_f[["TIMESTAMP"] + vars_sel].copy()

        file = asksaveasfilename(defaultextension=".csv")
        if file:
            df_export.to_csv(file, index=False)
            messagebox.showinfo("Exportado", "CSV guardado correctamente")
    
    def crear_hover(self):
        self.hover_annot = self.ax.annotate(
            "",xy=(0, 0),xytext=(15, 15),textcoords="offset points",
            bbox=dict(boxstyle="round", fc="white", ec="black"),
            arrowprops=dict(arrowstyle="->")
            )
        self.hover_annot.set_visible(False)
    
    # Placeholder hover function
    def on_hover(self, event):
        if self.block_hover:
            return

        #print("[Hover]")
        if (
            self.df_filtrado is None or
            not self.vars_sel or
            event.inaxes != self.ax or
            event.xdata is None
        ):
            for a in self.hover_annot.values():
                a.set_visible(False)
            self.canvas.draw_idle()
            return


        xdata = self.df_filtrado["TIMESTAMP"]
        x_num = mdates.date2num(xdata)
        idx = np.abs(x_num - event.xdata).argmin()

        x = xdata.iloc[idx]

        for a in self.hover_annot.values():
            a.set_visible(False)

        for v in self.vars_sel:
            if v not in self.df_filtrado.columns:
                continue
            if v not in self.hover_point:
                continue

            if v not in self.hover_annot:
                continue
            y = self.df_filtrado[v].iloc[idx]

            point = self.hover_point[v]
            annot = self.hover_annot[v]

            point.set_data([x], [y])

            texto = f"{x.strftime('%Y-%m-%d %H:%M')}\n{v}: {y:.2f}"

            annot.xy = (x, y)
            annot.set_text(texto)
            annot.set_visible(True)

        self.canvas.draw_idle()

    def on_close_app(self):
        salir = messagebox.askyesno("Salir", "¿Estás seguro de salir del programa?")
        if salir:
            self.is_closing = True
            try:
                self.root.quit()
                self.root.after(50, self.root.destroy)
            except:
                pass

# -------------------- Run App --------------------
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("BSRN_igf Dashboard")
root.geometry("1700x950")
root.minsize(1400, 850)

def report_callback_exception(exc, val, tb):
    msg = ''.join(traceback.format_exception(exc, val, tb))

    # Ignorar errores al cerrar
    if "application has been destroyed" in msg:
        return
    if "invalid command name" in msg and ("check_dpi_scaling" in msg or "update" in msg or "click_animation" in msg):
        return

    print(msg)

root.report_callback_exception = report_callback_exception       

DashboardApp(root)

root.mainloop()