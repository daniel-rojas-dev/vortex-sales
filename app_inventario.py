import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime 
import os 

# ==========================================
# CLASE DE BASE DE DATOS (MODELO)
# ==========================================
class InventarioDB:
    def __init__(self, db_name="inventario.db"):
        # Establecemos conexión y activamos el cursor
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.crear_tablas()

    def crear_tablas(self):
        # Tabla de Productos con columna para Código de Barras
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE,
                nombre TEXT UNIQUE,
                precio REAL,
                stock INTEGER
            )
        ''')
        # Tabla de Ventas para el historial financiero
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_hora TEXT,
                metodo_pago TEXT,
                monto REAL,
                referencia TEXT
            )
        ''')
        self.conn.commit()

    def buscar_producto(self, termino):
        """
        Busca por código exacto o nombre aproximado (sin importar mayúsculas).
        LOWER(?) convierte el término de búsqueda a minúsculas para comparar.
        """
        termino_limpio = termino.strip().lower()
        # Primero intentamos buscar por código de barras exacto
        self.cursor.execute("SELECT * FROM productos WHERE LOWER(codigo) = ?", (termino_limpio,))
        resultado = self.cursor.fetchone()
        
        if resultado:
            return [resultado] # Lo devolvemos en lista para mantener consistencia
        
        # Si no hay código, buscamos por nombre (similar)
        query = f"%{termino_limpio}%"
        self.cursor.execute("SELECT * FROM productos WHERE LOWER(nombre) LIKE ?", (query,))
        return self.cursor.fetchall()

    def registrar_venta_db(self, metodo, monto, ref="N/A"):
        """Guarda el movimiento financiero en la tabla de ventas."""
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute('''
            INSERT INTO ventas (fecha_hora, metodo_pago, monto, referencia)
            VALUES (?, ?, ?, ?)
        ''', (ahora, metodo, monto, ref))
        self.conn.commit()

    def agregar_o_actualizar_producto(self, codigo, nombre, precio, stock):
        """Inserta un nuevo producto o actualiza el stock si ya existe el nombre."""
        # Buscamos si ya existe
        self.cursor.execute("SELECT * FROM productos WHERE LOWER(nombre) = ?", (nombre.lower(),))
        producto = self.cursor.fetchone()
        
        if producto:
            nuevo_stock = producto[4] + stock
            self.cursor.execute("UPDATE productos SET stock = ?, precio = ?, codigo = ? WHERE id = ?", 
                                (nuevo_stock, precio, codigo, producto[0]))
        else:
            self.cursor.execute("INSERT INTO productos (codigo, nombre, precio, stock) VALUES (?, ?, ?, ?)", 
                                (codigo, nombre, precio, stock))
        self.conn.commit()

    def restar_stock(self, nombre, cantidad):
        """Resta la cantidad vendida del inventario actual."""
        self.cursor.execute("SELECT stock FROM productos WHERE nombre = ?", (nombre,))
        stock_actual = self.cursor.fetchone()[0]
        nuevo_stock = stock_actual - cantidad
        self.cursor.execute("UPDATE productos SET stock = ? WHERE nombre = ?", (nuevo_stock, nombre))
        self.conn.commit()

    def eliminar_producto(self, nombre):
        self.cursor.execute("DELETE FROM productos WHERE nombre = ?", (nombre,))
        self.conn.commit()

    def obtener_ventas_hoy(self):
        hoy = datetime.now().strftime("%Y-%m-%d")
        # Buscamos ventas que COMIENCEN con la fecha de hoy
        self.cursor.execute("""
            SELECT fecha_hora, metodo_pago, monto, referencia 
            FROM ventas 
            WHERE fecha_hora LIKE ?
        """, (f"{hoy}%",))
        return self.cursor.fetchall()

# ==========================================
# CLASE DE LA INTERFAZ GRÁFICA (VISTA/CONTROLADOR)
# ==========================================
class AplicacionInventario:
    def __init__(self, root):
        self.root = root
        self.root.title("Vortex Sales - Gestión de Ventas")
        self.root.geometry("750x800")
        
        self.db = InventarioDB()
        self.producto_actual = None 
        self.crear_interfaz()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    
    # ==========================================
    # LÓGICA DE BÚSQUEDA Y SELECCIÓN
    # ==========================================
    
    def ejecutar_busqueda(self):
        termino = self.entry_buscar.get().strip()
        if not termino: return
        
        resultados = self.db.buscar_producto(termino)
        
        if not resultados:
            messagebox.showinfo("Búsqueda", f"No se encontró nada para: {termino}")
            self.lbl_resultado.config(text="No encontrado", fg="red")
        elif len(resultados) == 1:
            # Si solo hay uno, lo seleccionamos de una vez
            self.seleccionar_producto(resultados[0])
        else:
            # ¡Aquí estaba el error! Ahora sí definimos la ventana
            self.ventana_seleccion_multiple(resultados)

    def ventana_seleccion_multiple(self, productos):
        """Crea una ventana emergente para elegir entre varios productos encontrados."""
        ventana_sel = tk.Toplevel(self.root)
        ventana_sel.title("Múltiples coincidencias")
        ventana_sel.geometry("400x350")
        ventana_sel.grab_set() # Bloquea la ventana principal

        tk.Label(ventana_sel, text="Se encontraron varios productos.\nSelecciona el correcto:", 
                 font=("Arial", 10, "bold"), pady=10).pack()

        # Creamos una lista visual
        lista_box = tk.Listbox(ventana_sel, font=("Arial", 11), width=45, height=10)
        lista_box.pack(padx=10, pady=10)

        # Metemos los productos en la lista (ID | Nombre | Precio)
        for p in productos:
            lista_box.insert(tk.END, f"{p[2]} - ${p[3]} (Stock: {p[4]})")

        def confirmar_seleccion():
            indice = lista_box.curselection()
            if indice:
                producto_elegido = productos[indice[0]]
                self.seleccionar_producto(producto_elegido)
                ventana_sel.destroy()
            else:
                messagebox.showwarning("Aviso", "Por favor, selecciona un producto.")

        tk.Button(ventana_sel, text="✅ Seleccionar", command=confirmar_seleccion, 
                  bg="lightblue", width=20, pady=5).pack(pady=10)

    def seleccionar_producto(self, p):
        """Carga el producto elegido en la memoria de la app para poder venderlo."""
        self.producto_actual = p
        # Estructura: (id, codigo, nombre, precio, stock)
        self.lbl_resultado.config(text=f"LISTO: {p[2]} | Stock: {p[4]} | ${p[3]}", fg="green")


    def crear_interfaz(self):
        # --- 1. SECCIÓN BUSCADOR ---
        frame_buscar = tk.LabelFrame(self.root, text="1. Buscador (Nombre o Código)", padx=10, pady=10)
        frame_buscar.pack(fill="x", padx=10, pady=5)

        self.entry_buscar = tk.Entry(frame_buscar, font=("Arial", 12))
        self.entry_buscar.grid(row=0, column=0, padx=5, sticky="we")
        # Permitir buscar al presionar 'Enter'
        self.entry_buscar.bind('<Return>', lambda e: self.ejecutar_busqueda())
        
        tk.Button(frame_buscar, text="🔍 Buscar", command=self.ejecutar_busqueda).grid(row=0, column=1, padx=5)

        self.lbl_resultado = tk.Label(frame_buscar, text="Esperando entrada...", fg="blue", font=("Arial", 10, "bold"))
        self.lbl_resultado.grid(row=1, column=0, columnspan=2, sticky="w", pady=5)

        tk.Button(frame_buscar, text="🛒 Añadir al Carrito", command=self.agregar_a_lista, bg="#e1f5fe").grid(row=0, column=2)

        # --- 2. SECCIÓN CARRITO ---
        frame_lista = tk.LabelFrame(self.root, text="2. Carrito de Compras", padx=10, pady=10)
        frame_lista.pack(fill="both", expand=True, padx=10, pady=5)

        self.tree_compras = ttk.Treeview(frame_lista, columns=("Nombre", "Precio", "Cant"), show="headings")
        self.tree_compras.heading("Nombre", text="Producto")
        self.tree_compras.heading("Precio", text="Unitario ($)")
        self.tree_compras.heading("Cant", text="Cant.")
        self.tree_compras.pack(fill="both", expand=True)

        # Botones de gestión rápida de lista
        btn_frame = tk.Frame(frame_lista)
        btn_frame.pack(fill="x", pady=5)
        tk.Button(btn_frame, text="❌ Quitar", command=self.eliminar_seleccionado, bg="#ffcdd2").pack(side="left", padx=5)
        tk.Button(btn_frame, text="🗑️ Vaciar", command=self.vaciar_carrito).pack(side="left")

        # --- 3. SECCIÓN BOTÓN DE VENTA ---
        tk.Button(self.root, text="💰 FINALIZAR Y COBRAR", command=self.procesar_venta, 
                  bg="#4CAF50", fg="white", font=("Arial", 14, "bold"), pady=15).pack(fill="x", padx=10, pady=10)

        # --- 4. SECCIÓN ADMIN (INVENTARIO) ---
        frame_admin = tk.LabelFrame(self.root, text="3. Panel de Administración", padx=10, pady=10)
        frame_admin.pack(fill="x", padx=10, pady=5)

        # Campos de entrada para gestión
        tk.Label(frame_admin, text="Cod. Barras:").grid(row=0, column=0)
        self.ent_cod = tk.Entry(frame_admin, width=15)
        self.ent_cod.grid(row=0, column=1)

        tk.Label(frame_admin, text="Nombre:").grid(row=0, column=2)
        self.ent_nom = tk.Entry(frame_admin, width=15)
        self.ent_nom.grid(row=0, column=3)

        tk.Label(frame_admin, text="Precio:").grid(row=0, column=4)
        self.ent_pre = tk.Entry(frame_admin, width=10)
        self.ent_pre.grid(row=0, column=5)

        tk.Label(frame_admin, text="Stock inicial:").grid(row=0, column=6)
        self.ent_sto = tk.Entry(frame_admin, width=10)
        self.ent_sto.grid(row=0, column=7)

        tk.Button(frame_admin, text="📊 Ver Reporte de Hoy", command=self.abrir_reporte_ventas, bg="#bbdefb").grid(row=1, column=9, columnspan=2, sticky="we", padx=5)
        tk.Button(frame_admin, text="📦 Guardar Producto", command=self.agregar_stock_db, bg="#eeeeee").grid(row=1, column=0, columnspan=8, sticky="we", pady=10)
        
    def abrir_reporte_ventas(self):
        ventana_rep = tk.Toplevel(self.root)
        ventana_rep.title("Reporte de Ventas - Hoy")
        ventana_rep.geometry("500x450")
        
        # Consultar datos
        ventas = self.db.obtener_ventas_hoy()
        
        # Etiquetas de Resumen
        total_efectivo = sum(v[2] for v in ventas if v[1] == "EFECTIVO")
        total_tarjeta = sum(v[2] for v in ventas if v[1] == "TARJETA")
        
        frame_resumen = tk.Frame(ventana_rep, pady=10)
        frame_resumen.pack()
        
        tk.Label(frame_resumen, text=f"💵 Efectivo: ${total_efectivo:.2f}", fg="green", font=("Arial", 10, "bold")).grid(row=0, column=0, padx=20)
        tk.Label(frame_resumen, text=f"💳 Tarjeta: ${total_tarjeta:.2f}", fg="blue", font=("Arial", 10, "bold")).grid(row=0, column=1, padx=20)
        tk.Label(ventana_rep, text=f"TOTAL CAJA: ${total_efectivo + total_tarjeta:.2f}", font=("Arial", 12, "bold")).pack(pady=5)

        # Tabla de detalles
        tabla_rep = ttk.Treeview(ventana_rep, columns=("Hora", "Metodo", "Monto"), show="headings", height=10)
        tabla_rep.heading("Hora", text="Fecha/Hora")
        tabla_rep.heading("Metodo", text="Método")
        tabla_rep.heading("Monto", text="Monto ($)")
        
        # Ajustar ancho de columnas
        tabla_rep.column("Hora", width=150)
        tabla_rep.column("Metodo", width=100)
        tabla_rep.column("Monto", width=80)
        tabla_rep.pack(padx=10, pady=10, fill="both", expand=True)

        for v in ventas:
            # v[0]=fecha, v[1]=metodo, v[2]=monto
            tabla_rep.insert("", "end", values=(v[0], v[1], f"{v[2]:.2f}"))

        if not ventas:
            tk.Label(ventana_rep, text="No hay ventas registradas hoy.", fg="red").pack()

    def seleccionar_producto(self, p):
        self.producto_actual = p
        # Formato: (id, codigo, nombre, precio, stock)
        self.lbl_resultado.config(text=f"SELECCIONADO: {p[2]} | Stock: {p[4]} | ${p[3]}", fg="green")

    def agregar_a_lista(self):
        if not self.producto_actual:
            messagebox.showwarning("Aviso", "Primero busca un producto.")
            return
        
        nombre, precio, stock_disponible = self.producto_actual[2], self.producto_actual[3], self.producto_actual[4]
        
        cant = simpledialog.askinteger("Cantidad", f"¿Cuántos '{nombre}' llevar?", minvalue=1, maxvalue=stock_disponible)
        if cant:
            self.tree_compras.insert("", "end", values=(nombre, precio, cant))
            self.entry_buscar.delete(0, tk.END)
            self.producto_actual = None

    def procesar_venta(self):
        items = self.tree_compras.get_children()
        if not items:
            messagebox.showwarning("Vacío", "El carrito no tiene productos.")
            return

        total = sum(float(self.tree_compras.item(i, 'values')[1]) * int(self.tree_compras.item(i, 'values')[2]) for i in items)
        
        # VENTANA DE PAGO MODAL
        win_pago = tk.Toplevel(self.root)
        win_pago.title("Cobro")
        win_pago.geometry("300x250")
        win_pago.grab_set()

        tk.Label(win_pago, text=f"Total: ${total:.2f}", font=("Arial", 14, "bold")).pack(pady=20)

        def pago_efectivo():
            entrega = simpledialog.askfloat("Efectivo", f"Total: ${total}\n¿Cuánto paga el cliente?", minvalue=total)
            if entrega:
                vuelto = entrega - total
                self.finalizar_todo(items, total, "EFECTIVO", f"Vuelto: ${vuelto:.2f}")
                win_pago.destroy()

        def pago_tarjeta():
            ref = simpledialog.askstring("Tarjeta", "Ingrese Número de Referencia:")
            if ref:
                self.db.registrar_venta_db("TARJETA", total, ref)
                self.finalizar_todo(items, total, "TARJETA", f"Ref: {ref}")
                win_pago.destroy()

        tk.Button(win_pago, text="💵 Efectivo", command=pago_efectivo, width=20, bg="lightgreen").pack(pady=5)
        tk.Button(win_pago, text="💳 Tarjeta", command=pago_tarjeta, width=20, bg="lightblue").pack(pady=5)

    def finalizar_todo(self, items, total, metodo, detalle):
        # 1. Registrar venta en historial (Si fue efectivo, registramos sin ref)
        if metodo == "EFECTIVO":
            self.db.registrar_venta_db(metodo, total)
        
        # 2. Descontar Inventario
        for i in items:
            nombre, _, cant = self.tree_compras.item(i, 'values')
            self.db.restar_stock(nombre, int(cant))
        
       # --- GENERACIÓN DEL TICKET FORMATEADO ---
        fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M")
        empresa = "TECH STORE S.A."
        separador = "=" * 30
        linea = "-" * 30

        # Encabezado
        ticket =  f"\n{separador}\n"
        ticket += f"{empresa.center(30)}\n"
        ticket += f"{'RIF: J-12345678-0'.center(30)}\n"
        ticket += f"Fecha: {fecha_actual}\n"
        ticket += f"{linea}\n"
        ticket += f"{'CANT  PRODUCTO'.ljust(20)} {'TOTAL'.rjust(9)}\n"
        ticket += f"{linea}\n"

        # Detalle de productos
        for i in items:
            nom, pre, cant = self.tree_compras.item(i, 'values')
            subtotal = float(pre) * int(cant)
            # Cortamos el nombre si es muy largo para que no rompa el ticket
            nombre_corto = (nom[:15] + '..') if len(nom) > 15 else nom
            ticket += f"{str(cant).ljust(4)}  {nombre_corto.ljust(15)} ${subtotal:>7.2f}\n"

        # Totales
        ticket += f"{linea}\n"
        ticket += f"{'TOTAL A PAGAR:'.ljust(20)} ${total:>7.2f}\n"
        ticket += f"{'METODO:'.ljust(20)} {metodo:>9}\n"
        ticket += f"{detalle.ljust(20)}\n" # Aquí sale el vuelto o la referencia
        ticket += f"{separador}\n"
        ticket += f"{'¡GRACIAS POR SU COMPRA!'.center(30)}\n"
        ticket += f"{separador}\n"

        # Imprimir en consola con estilo
        print(ticket)
        
        # Opcional: Mostrarlo en un cuadro de mensaje
        messagebox.showinfo("Ticket de Venta", ticket)

        # 1. Crear carpeta de facturas si no existe
        if not os.path.exists("facturas"):
            os.makedirs("facturas")

        # 2. Crear un nombre único (usando la hora exacta para no repetir)
        # Formato: Año_Mes_Día_Hora_Minuto_Segundo
        id_unico = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
        nombre_archivo = f"facturas/ticket_{id_unico}.txt"

        # 3. Guardar el archivo
        with open(nombre_archivo, "w", encoding="utf-8") as archivo:
            archivo.write(ticket)
        
        print(f"💾 Ticket guardado como: {nombre_archivo}")

    def agregar_stock_db(self):
        try:
            c, n = self.ent_cod.get().strip(), self.ent_nom.get().strip()
            p, s = float(self.ent_pre.get()), int(self.ent_sto.get())
            if not c or not n: raise ValueError
            self.db.agregar_o_actualizar_producto(c, n, p, s)
            messagebox.showinfo("Admin", "Producto guardado/actualizado correctamente.")
            for e in [self.ent_cod, self.ent_nom, self.ent_pre, self.ent_sto]: e.delete(0, tk.END)
        except:
            messagebox.showerror("Error", "Verifica los datos (Precio y Stock deben ser números).")

    def eliminar_seleccionado(self):
        for s in self.tree_compras.selection(): self.tree_compras.delete(s)

    def vaciar_carrito(self):
        for i in self.tree_compras.get_children(): self.tree_compras.delete(i)

    def on_closing(self):
        self.db.conn.close() # Cerramos la conexión a la DB
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    root.state('zoomed')
    app = AplicacionInventario(root)
    root.mainloop()
    