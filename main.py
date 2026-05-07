#Tomamos la funciones previamente creadas y agregamos una interfaz con tkinter
import pandas as pd 
import numpy as np 
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg,NavigationToolbar2Tk
import plotly.express as px 
from tkinter import *
from tkinter import ttk
from tkinter.filedialog import askopenfilename,asksaveasfilename
from datetime import datetime
import tkinter.messagebox as messagebox
from tkcalendar import DateEntry
import matplotlib.dates as mdates

plt.style.use("seaborn-v0_8-whitegrid")

#----------------Seleccion de datos------------- 
def seleccion_datos():
    #Ventana de tkinter
    Tk().withdraw()
    #Explorador de archivos
    filename = askopenfilename(
        title="Selecciona un archivo CSV",
        filetypes=[("Archivos CSV", "*.csv")]
        
    )
    if not filename:
        return None 
    return pd.read_csv(filename)

#----------limpieza de datos eliminando los -999.9 y -999.0------
def limpieza(df):
    return df.replace([-999.9,-999.0],np.nan)

#----------------preprocesamiento de datos------------- 
def preprocesamiento(df):
   #Convertimos las columna timestamp Formato

   df['TIMESTAMP'] = pd.to_datetime(df['TIMESTAMP'],dayfirst = True)
    #Convertimos los datos a numericos 
   numeric_cols = df.columns.drop('TIMESTAMP')
   df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric,errors='coerce')

   #Conversion de temperatura de columnas 
   for col in ['CRPTemp_Avg','UVTEMP_Avg','DEW_POINT_Avg']:
       if col in df.columns:
           df[col] = df[col]+273.15

    #Calculos derivados 
   if set(['GH_CALC_Avg','GLOBAL_Avg']).issubset(df.columns):
       df['dif_GH_CALC_GLOBAL'] = df['GH_CALC_Avg']-df['GLOBAL_Avg']
       df['ratio_GH_CALC_GLOBAL']=df['GH_CALC_Avg']/df['GLOBAL_Avg']
       df['abs_dif_GH_CALC_GLOBAL'] = abs(df['dif_GH_CALC_GLOBAL'])
       df['pct_dif_GH_CALC_GLOBAL'] = np.where(
           df['GLOBAL_Avg'] !=0, (df['dif_GH_CALC_GLOBAL']/df['GLOBAL_Avg'])*100,np.nan)
       

   if set(['DIFFUSE_Avg', 'DIRECT_Avg']).issubset(df.columns):
       df['sum_SW'] = df['DIFFUSE_Avg'] +df['DIRECT_Avg']*np.cos(np.radians(df['ZenDeg']))
       df['percent'] = 0.01*df['sum_SW']
   return df 

#--------------------------Grupos--------------------- 
groups = {
    "1. Parámetros Básicos": ["GLOBAL_Avg","DIRECT_Avg","DIFFUSE_Avg","GH_CALC_Avg","percent"],
    "2. Balance de onda corta": ["GLOBAL_Avg","UPWARD_SW_Avg"],
    "3. Balance de onda larga": ["DOWNWARD_Avg","UPWARD_LW_Avg","DWIRTEMP_Avg","UWIRTEMP_Avg","CRPTemp_Avg"],
    "4. Meteorología": ["CRPTemp_Avg","RELATIVE_HUMIDITY_Avg","PRESSURE_Avg","DEW_POINT_Avg"],
    "5. Ultravioleta": ["UVB_Avg","UVTEMP_Avg","UVSIGNAL_Avg"],
    "6. Dispersión": ["dif_GH_CALC_GLOBAL","abs_dif_GH_CALC_GLOBAL","pct_dif_GH_CALC_GLOBAL","ratio_GH_CALC_GLOBAL","sum_SW"]
}


#-----------------Insertamos la interfaz de tkinter-----------

class App:
    contador = 1
    def __init__(self,notebook):

        self.notebook = notebook
        self.root = Frame(self.notebook)
        self.root.app = self
        self.root.estado ={}
        self.notebook.add(self.root,text=f"consulta{App.contador}")
        self.notebook.select(self.root)
        App.contador +=1

        self.df = None
        self.df_filtrado = None
        self.dark_mode = False 
        self.pagina = 0
        self.filas_por_pagina = 500


        #-----------Panel derecho-----------
        self.sidebar = Frame(self.root, width=320, bg="#ffffff")
        self.sidebar.pack(side=LEFT, fill=Y)

        Label(self.sidebar, text="BSRN_igf",
              font=("Segoe UI", 14, "bold"), bg="#ffffff").pack(pady=15)

        ttk.Button(self.sidebar, text="Cargar CSV", command=self.cargar_csv)\
            .pack(padx=15, pady=5)

        self.combo = ttk.Combobox(
            self.sidebar, values=list(groups.keys()),
            state="readonly", width=30
        )
        self.combo.pack(padx=10)
        self.combo.bind("<<ComboboxSelected>>", self.actualizar_variables)

        ttk.Label(self.sidebar, text="Variables").pack(anchor="w", padx=15)
        self.listbox_vars = Listbox(self.sidebar, selectmode=MULTIPLE, height=6)
        self.listbox_vars.pack(padx=10, pady=5)
        self.listbox_vars.bind("<<ListboxSelect>>", lambda e: self.previsualizar())

        #-----------Fechas------
        ttk.Label(self.sidebar,text="Fecha inicio").pack(anchor="w",padx=10)
        frame_ini = Frame(self.sidebar, bg="#ffffff")
        frame_ini.pack(anchor="w",padx=10)

        self.fecha_inicio = DateEntry(frame_ini,width=12)
        self.fecha_inicio.pack(side=LEFT)
        self.hora_ini = Spinbox(frame_ini,from_=0,to=23,width=3,format="%02.0f",
                                command=self.previsualizar)
        self.min_ini = Spinbox(frame_ini,from_=0,to=59,width=3,format="%02.0f",
                               command=self.previsualizar)
        self.hora_ini.pack(side=LEFT,padx=2)
        self.min_ini.pack(side=LEFT)

        ttk.Label(self.sidebar, text="Fecha fin").pack(anchor="w",padx=10,pady=(8,0))
        frame_fin = Frame(self.sidebar,bg="#ffffff")
        frame_fin.pack(anchor="w",padx=10)

        self.fecha_fin = DateEntry(frame_fin,width=12)
        self.fecha_fin.pack(side=LEFT)
        self.hora_fin = Spinbox(frame_fin, from_=0,to=23,width=3,format="%02.0f",
                                command=self.previsualizar)
        self.min_fin = Spinbox(frame_fin,from_=0,to=59,width=3,format="%02.0f",
                               command=self.previsualizar)
        self.hora_fin.pack(side=LEFT,padx=2)
        self.min_fin.pack(side=LEFT)

        ttk.Button(self.sidebar,text="Consultar tabla", command=self.consultar_tabla).pack(pady=5)
        ttk.Button(self.sidebar,text="Graficar", command=self.grafica_plotly).pack(pady=8)
        ttk.Button(self.sidebar,text="Exportar CSV", command=self.exportar_csv).pack(pady=5) 
        ttk.Button(self.sidebar,text="Nueva consulta", command=self.nueva_consulta).pack(pady=20)

        #---------Configuracion----------
 
        self.main = Frame(self.root, bg="#eef2f7")
        self.main.pack(side=LEFT, fill=BOTH, expand=True)

        Button(self.main, text="🌙", command=self.toggle_dark).pack(anchor="ne", padx=8, pady=4)
        
        frame_plot = Frame(self.main)
        frame_plot.pack(fill=X,padx=10, pady=(10,0))
        
        self.fig, self.ax = plt.subplots(figsize=(12,5))
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame_plot)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=X, padx=10, pady=10)

       # --- Punto inteligente (Hover) ---
        self.hover_point = {}
        self.hover_annot = {}
        self.vars_sel = []
        self.estado = {}
        self.canvas.mpl_connect("motion_notify_event", self.on_hover)

        frame_toolbar= Frame(self.main)
        frame_toolbar.pack(fill=X, padx=10)

        self.toolbar = NavigationToolbar2Tk(self.canvas,frame_toolbar)
        self.toolbar.update()

        self.tree=ttk.Treeview(self.main,show="headings")
        self.tree.pack(fill=BOTH,expand=True,padx=10,pady=5)

        self.nav = Frame(self.main)
        self.nav.pack(pady=5)
        Button(self.nav,text="◀ Anterior", command=self.prev_page).pack(side=LEFT,padx=5)
        Button(self.nav, text="Siguiente ▶", command=self.next_page).pack(side=LEFT,padx=5)

     #-------------------Funcionamiento-----

    def cargar_csv(self):
        df = seleccion_datos()
        if df is None:
            return
        self.df = preprocesamiento(limpieza(df))
        messagebox.showinfo("OK", "Datos cargados correctamente")

    def actualizar_variables(self, _):
        self.listbox_vars.delete(0, END)
        for v in groups[self.combo.get()]:
            self.listbox_vars.insert(END, v)

    def obtener_filtro(self):
        inicio = datetime(
            self.fecha_inicio.get_date().year,
            self.fecha_inicio.get_date().month,
            self.fecha_inicio.get_date().day,
            int(self.hora_ini.get()), int(self.min_ini.get()),0
        )
        fin = datetime(
            self.fecha_fin.get_date().year,
            self.fecha_fin.get_date().month,
            self.fecha_fin.get_date().day,
            int(self.hora_fin.get()), int(self.min_fin.get()),59
        )

        if fin < inicio:
            messagebox.showerror("Error","La fecha fin no puede ser menor")
            return None

        return self.df.loc[
            (self.df["TIMESTAMP"] >= inicio) &
            (self.df["TIMESTAMP"] <= fin)
        ].copy()
    
    def on_hover(self, event):
        if (
            self.df_filtrado is None or
            not self.vars_sel or
            event.inaxes != self.ax or
            event.xdata is None 
        ):
            return

        xdata = self.df_filtrado["TIMESTAMP"]
        x_num = mdates.date2num(xdata)
        idx = np.abs(x_num - event.xdata).argmin()
        x = xdata.iloc[idx]

        for v in self.vars_sel:
            y = self.df_filtrado[v].iloc[idx]
            point = self.hover_point[v]
            annot = self.hover_annot[v]
            point.set_data([x],[y])
            texto = f"{x.strftime('%Y-%m-%d %H:%M')}\n{v}:{y:.2f}"
            annot.xy = (x,y)
            annot.set_text(texto)
            annot.set_visible(True)
        self.canvas.draw_idle()    


    
    def guardar_estado(self):

        if self.df_filtrado is None:
            return

        self.root.estado = {

        "grupo": self.combo.get(),

        "variables":
        [self.listbox_vars.get(i)
        for i in self.listbox_vars.curselection()],

        "fecha_inicio": self.fecha_inicio.get_date(),

        "fecha_fin": self.fecha_fin.get_date(),

        "hora_ini": self.hora_ini.get(),

        "min_ini": self.min_ini.get(),

        "hora_fin": self.hora_fin.get(),

        "min_fin": self.min_fin.get(),

        "df_filtrado": self.df_filtrado

    } 

    def on_tab_change(self,event):
        tab = event.widget.nametowidget(event.widget.select())

        if not hasattr(tab,"estado"):
            return
        estado = tab.estado

        if not estado:
            return
       # restaurar grupo
        self.combo.set(estado["grupo"])
        self.actualizar_variables(None)

        # restaurar variables
        for i,v in enumerate(groups[estado["grupo"]]):
            if v in estado["variables"]:
                self.listbox_vars.selection_set(i)

        # restaurar fechas
        self.fecha_inicio.set_date(estado["fecha_inicio"])
        self.hora_ini.delete(0,END)
        self.hora_ini.insert(0,estado["hora_ini"])
        self.min_ini.delete(0,END)
        self.min_ini.insert(0,estado["min_ini"])
        self.fecha_fin.set_date(estado["fecha_fin"])
        self.hora_fin.delete(0,END)
        self.hora_fin.insert(0,estado["hora_fin"])
        self.min_fin.delete(0,END)
        self.min_fin.insert(0,estado["min_fin"])
        self.df_filtrado = estado["df_filtrado"]
        self.previsualizar()          


    def previsualizar(self):
        if self.df is None:
            return
        self.vars_sel = [self.listbox_vars.get(i) for i in self.listbox_vars.curselection()]
        if not self.vars_sel:
            return

        df_f = self.obtener_filtro()
        if df_f is None or df_f.empty:
            return

        self.df_filtrado = df_f

        self.ax.clear()
        self.hover_point.clear()
        self.hover_annot.clear()

        for v in self.vars_sel:
            line,= self.ax.plot(self.df_filtrado["TIMESTAMP"],
                                self.df_filtrado[v],label=v)
            color = line.get_color()

            point, = self.ax.plot( [], [], "o", color=color,
                                 markersize=7,zorder=10)

            annot = self.ax.annotate("",xy=(0, 0),xytext=(15, 15),
                                     textcoords="offset points",
                                     bbox=dict(boxstyle="round", fc="white"),
                                     arrowprops=dict(arrowstyle="->"))
            
            annot.set_visible(False)
            self.hover_point[v] = point
            self.hover_annot[v] = annot
     
        self.ax.legend(
            loc="upper left",
            bbox_to_anchor=(1.02, 1),
            borderaxespad=0,
            fontsize=9
            )
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m-%Y'))
        self.ax.xaxis.set_major_locator(
        mdates.AutoDateLocator()
        )  

        self.fig.autofmt_xdate()
        self.fig.tight_layout()
        self.canvas.draw()  
        self.guardar_estado()
        
    def consultar_tabla(self):
        if self.df is None:
            messagebox.showwarning("Aviso", "No hay datos cargados")
            return

        vars_sel = [self.listbox_vars.get(i) for i in self.listbox_vars.curselection()]
        if not vars_sel:
            messagebox.showwarning("Aviso", "Selecciona al menos una variable")
            return

        df_f = self.obtener_filtro()
        if df_f is None or df_f.empty:
            messagebox.showwarning("Aviso", "No hay datos para mostrar")
            return

        self.df_filtrado = df_f[["TIMESTAMP"] + vars_sel].copy()

        self.pagina = 0
        self.actualizar_tabla()
        self.guardar_estado()

    def actualizar_tabla(self):
        self.tree.delete(*self.tree.get_children())

        inicio = self.pagina * self.filas_por_pagina
        fin = inicio + self.filas_por_pagina
        df_page = self.df_filtrado.iloc[inicio:fin]

        self.tree["columns"] = list(df_page.columns)
        for col in df_page.columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=140)

        for _, row in df_page.iterrows():
            self.tree.insert("", END, values=list(row))

    def next_page(self):
        if (self.pagina + 1) * self.filas_por_pagina < len(self.df_filtrado):
            self.pagina += 1
            self.actualizar_tabla()

    def prev_page(self):
        if self.pagina > 0:
            self.pagina -= 1
            self.actualizar_tabla()        

    def grafica_plotly(self):
        if self.df_filtrado is not None:
            px.line(self.df_filtrado,x="TIMESTAMP",
                    y=[self.listbox_vars.get(i) for i in self.listbox_vars.curselection()]).show()

    def exportar_csv(self):
        if self.df_filtrado is None:
            messagebox.showwarning("Aviso", "No hay datos filtrados")
            return
        file = asksaveasfilename(defaultextension=".csv")
        if file:
            self.df_filtrado.to_csv(file, index=False)
            messagebox.showinfo("Exportado", "CSV guardado correctamente")

    def nueva_consulta(self):
        App(self.notebook)

    def toggle_dark(self):
        self.dark_mode = not self.dark_mode
        bg = "#2b2b2b" if self.dark_mode else "#ffffff"
        fg = "#ffffff" if self.dark_mode else "#000000"

        self.sidebar.configure(bg=bg)
        self.main.configure(bg=bg)
        self.root.configure(bg=bg)

#--------------------Inicio aplicacion----------
def cambio_tab(event):
    notebook = event.widget
    tab = notebook.nametowidget(notebook.select())
    if not hasattr(tab,"app"):
        return
    app = tab.app
    estado = tab.estado
    if not estado:
        return
    app.combo.set(estado["grupo"])
    app.actualizar_variables(None)
    app.listbox_vars.selection_clear(0, "end")

    vars_grupo = groups[estado["grupo"]]

    for i in range(len(vars_grupo)):

        if vars_grupo[i] in estado["variables"]:
            app.listbox_vars.selection_set(i)
    app.fecha_inicio.set_date(estado["fecha_inicio"])
    app.fecha_fin.set_date(estado["fecha_fin"])
    app.hora_ini.delete(0,END)
    app.hora_ini.insert(0,estado["hora_ini"])
    app.min_ini.delete(0,END)
    app.min_ini.insert(0,estado["min_ini"])
    app.hora_fin.delete(0,END)
    app.hora_fin.insert(0,estado["hora_fin"])
    app.min_fin.delete(0,END)
    app.min_fin.insert(0,estado["min_fin"])
    app.df_filtrado = estado["df_filtrado"]
    app.previsualizar()


root = Tk()
root.title("BSRN_igf")
root.geometry("1700x950")
root.minsize(1700,950)
notebook = ttk.Notebook(root)
notebook.pack(fill = "both",expand=True)
notebook.bind("<<NotebookTabChanged>>", cambio_tab)
App(notebook)
root.mainloop()
