
import customtkinter as ctk
import tkinter as tk
from tkinter.filedialog import askopenfilename, asksaveasfilename
import tkinter.messagebox as messagebox

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.dates as mdates
import plotly.express as px
from tksheet import Sheet
from datetime import datetime
from tkcalendar import DateEntry


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

        self.hover_annot = None
        self.hover_points = []

        self.df_tabla = None
        self.lines = []

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

        btn_frame = ctk.CTkFrame(self.sidebar_scroll, fg_color="transparent")
        btn_frame.pack(padx=5, pady=(0, 5), fill="x")

        ctk.CTkButton(btn_frame, text="Seleccionar todo", command=self.select_all_vars)\
            .pack(side="left", padx=(0, 5), fill="x", expand=True)

        ctk.CTkButton(btn_frame, text="Limpiar", fg_color="gray30",
                  hover_color="gray40", command=self.clear_vars)\
            .pack(side="left", padx=(5, 0), fill="x", expand=True)

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

        ctk.CTkButton(bottom_actions, text="Graficar", command=self.previsualizar)\
            .pack(fill="x", pady=5)

        ctk.CTkButton(bottom_actions, text="Exportar CSV", command=self.exportar_csv)\
            .pack(fill="x", pady=5)


    # ---------------- Main UI ----------------
    def toolbar_zoom(self):
        self.mpl_toolbar.zoom()

    def toolbar_pan(self):
        self.mpl_toolbar.pan()

    def toolbar_home(self):
        self.mpl_toolbar.home()

    def toolbar_save(self):
        self.mpl_toolbar.save_figure()
   
   
   
    def build_main(self):
        # Top bar
        top_bar = ctk.CTkFrame(self.main, fg_color="transparent")
        top_bar.pack(fill="x", padx=15, pady=(10, 5))

        self.status_label = ctk.CTkLabel(top_bar, text="Ready", text_color="gray")
        self.status_label.pack(side="left")

        self.dark_switch = ctk.CTkSwitch(top_bar, text="Dark Mode", command=self.toggle_dark)
        self.dark_switch.pack(side="right")

        # Plot area
        frame_plot = ctk.CTkFrame(self.main)
        frame_plot.pack(fill="x", padx=15, pady=(10, 5))

        self.fig, self.ax = plt.subplots(figsize=(12, 5))
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame_plot)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="x", padx=10, pady=10)


        self.mpl_toolbar = NavigationToolbar2Tk(self.canvas, self.main)
        self.mpl_toolbar.update()
        self.mpl_toolbar.pack_forget()

        self.hover_annot = self.ax.annotate("",xy=(0, 0),xytext=(15, 15),
                                            textcoords="offset points",bbox=dict(boxstyle="round", fc="white", ec="black"),
                                            arrowprops=dict(arrowstyle="->"))
        self.hover_annot.set_visible(False)



        self.canvas.mpl_connect("motion_notify_event", self.on_hover)

        toolbar = ctk.CTkFrame(self.main, fg_color="transparent")
        toolbar.pack(fill="x", padx=15, pady=(0, 5))

        ctk.CTkButton(toolbar, text="Zoom", width=90, command=lambda: self.toolbar_zoom()).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Pan", width=90, command=lambda: self.toolbar_pan()).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Reset", width=90, command=lambda: self.toolbar_home()).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Guardar", width=90, command=lambda: self.toolbar_save()).pack(side="left", padx=5)

        self.crear_hover()
        
        # Table (temporary placeholder)
        self.table_frame = ctk.CTkFrame(self.main)
        self.table_frame.pack(fill="both", expand=True, padx=15, pady=(5, 10))


        self.sheet = Sheet(self.table_frame)
        self.sheet.pack(fill="both", expand=True)
        self.sheet.enable_bindings((
            "single_select",
            "row_select",
            "column_select",
            "column_width_resize",
            "arrowkeys",
            "right_click_popup_menu",
            "rc_select",
            "copy"
            ))
        
        self.apply_table_theme()

    def build_tab_bar(self):
        left = ctk.CTkFrame(self.top_tabs, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=10, pady=8)

        self.tabs_scroll = ctk.CTkScrollableFrame(left, height=40, orientation="horizontal")
        self.tabs_scroll.pack(side="left", fill="x", expand=True)

        right = ctk.CTkFrame(self.top_tabs, fg_color="transparent")
        right.pack(side="right", padx=10, pady=8)

        ctk.CTkButton(right,text="+ Nueva",width=90,
                      command=self.nueva_consulta).pack(side="right", padx=5)

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

        for q in self.queries:
            is_active = (q == self.current_query)

            tab_frame = ctk.CTkFrame(self.tabs_scroll,corner_radius=12,
                                     fg_color="gray30" if is_active else "transparent")
            tab_frame.pack(side="left", padx=5, pady=5)

            btn_tab = ctk.CTkButton(tab_frame,text=q.name,fg_color="transparent",
                                    hover_color="gray40",command=lambda query=q: self.select_query(query),
                                    width=130)
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

    def select_query(self, query):
        self.guardar_estado_actual()
        self.current_query = query

        self.ax.clear()
        self.apply_plot_theme()
        self.canvas.draw_idle()

        self.cargar_estado_query()
        self.refresh_query_list()

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
        q.df_tabla = self.df_tabla

    def cargar_estado_query(self):
        q = self.current_query
        if q is None:
            return

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

        if q.df_tabla is not None:
            self.sheet.headers(list(q.df_tabla.columns))
            self.sheet.set_sheet_data(q.df_tabla.values.tolist())
            self.sheet.set_all_column_widths()
            self.sheet.refresh()
            self.sheet.redraw()
        else:
            self.sheet.set_sheet_data([])
            self.sheet.headers([])
            self.sheet.refresh()
            self.sheet.redraw()

        if self.df is not None:
            self.previsualizar()

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
            self.apply_table_theme()
            self.sheet.refresh()
            self.sheet.redraw()
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
    def apply_table_theme(self):
        dark = (self.dark_switch.get() == 1)

        if dark:
            self.sheet.set_options(
                table_bg="#1e1e1e",
                table_fg="white",
                header_bg="#2b2b2b",
                header_fg="white",
                index_bg="#2b2b2b",
                index_fg="white",
                top_left_bg="#2b2b2b",
                top_left_fg="white"
            )
        else:
            self.sheet.set_options(
                table_bg="white",
                table_fg="black",
                header_bg="#f0f0f0",
                header_fg="black",
                index_bg="#f0f0f0",
                index_fg="black",
                top_left_bg="#f0f0f0",
                top_left_fg="black"
            )
        self.sheet.refresh()
        self.sheet.redraw()
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
        if self.df is None:
            return

        vars_sel = self.get_selected_vars()

        df_f = self.obtener_filtro()
        if df_f is None or df_f.empty:
            self.ax.clear()
            self.lines = []
            self.canvas.draw_idle()
            return

        self.df_filtrado = df_f

        self.ax.clear()
        self.lines = []
        self.apply_plot_theme()

        for v in vars_sel:
            if v not in self.df_filtrado.columns:
                continue                

            line, =self.ax.plot(self.df_filtrado["TIMESTAMP"],self.df_filtrado[v],label=v)
            self.lines.append((v,line))

        if not self.lines:
            self.canvas.draw_idle()
            return

        self.ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), fontsize=9)  
        self.fig.autofmt_xdate()
        self.fig.tight_layout()
        self.canvas.draw_idle()


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

        self.sheet.set_sheet_data([])
        self.sheet.headers([])

        self.sheet.headers(list(self.df_filtrado.columns))
        self.sheet.set_sheet_data(self.df_filtrado.values.tolist())

        self.sheet.refresh()
        self.sheet.set_all_column_widths()
        self.sheet.redraw()

        self.df_tabla = self.df_filtrado.copy()
        self.current_query.df_tabla = self.df_tabla
        self.guardar_estado_actual()

    def grafica_plotly(self):
        if self.df_filtrado is not None:
            vars_sel = self.get_selected_vars()
            if vars_sel:
                px.line(self.df_filtrado, x="TIMESTAMP", y=vars_sel).show()

    def exportar_csv(self):
        if self.df_filtrado is None:
            messagebox.showwarning("Aviso", "No hay datos filtrados")
            return

        file = asksaveasfilename(defaultextension=".csv")
        if file:
            self.df_filtrado.to_csv(file, index=False)
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

        if not hasattr(self,"lines") or not self.lines:
            return
        if self.df_filtrado is None:
            return

        if event.inaxes != self.ax:
            if self.hover_annot:
                self.hover_annot.set_visible(False)
                self.canvas.draw_idle()
            return

        visible = False

        for var,line in self.lines:
            cont,ind = line.contains(event)
            if cont:
                idx = ind["ind"][0]

                x = self.df_filtrado["TIMESTAMP"].iloc[idx]
                y = self.df_filtrado[var].iloc[idx]


                texto = f"{var}\n{x.strftime('%Y-%m-%d %H:%M')}\n{y:.2f}"

                self.hover_annot.xy = (mdates.date2num(x), y)
                self.hover_annot.set_text(texto)
                self.hover_annot.set_visible(True)

                visible = True
                break

        if not visible:
            self.hover_annot.set_visible(False)

        self.canvas.draw_idle()
        


# -------------------- Run App --------------------
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("BSRN_igf Dashboard")
root.geometry("1700x950")
root.minsize(1400, 850)

DashboardApp(root)

root.mainloop()