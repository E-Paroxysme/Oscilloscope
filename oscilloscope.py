import sys
import time
import numpy as np
import serial
import serial.tools.list_ports
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                           QPushButton, QComboBox, QLabel, QSpinBox, QDoubleSpinBox,
                           QCheckBox, QGroupBox, QGridLayout, QFileDialog, QMessageBox)
from PyQt5.QtCore import QTimer, Qt
import pyqtgraph as pg

class OscilloscopeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Oscilloscope PC")
        self.resize(1000, 700)
        
        # Variables pour les données
        self.serial_port = None
        self.is_connected = False
        self.is_capturing = False
        self.is_real_time = True
        self.capture_data = []
        self.real_time_data = []
        self.max_data_points = 1000  # Nombre maximum de points pour l'affichage en temps réel
        self.capture_duration = 5.0  # Durée de capture en secondes
        self.sample_rate = 100  # Taux d'échantillonnage en Hz
        
        # Configuration de l'interface
        self.setup_ui()
        
        # Timer pour la mise à jour de l'affichage
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plot)
        self.update_timer.start(50)  # Mise à jour toutes les 50ms
        
        # Timer pour la lecture des données série
        self.serial_timer = QTimer()
        self.serial_timer.timeout.connect(self.read_serial_data)
        self.serial_timer.start(10)  # Lecture toutes les 10ms
        
    def setup_ui(self):
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Panneau supérieur pour les contrôles
        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)
        
        # Groupe pour la connexion série
        serial_group = QGroupBox("Connexion Série")
        serial_layout = QGridLayout(serial_group)
        
        # Sélection du port série
        self.port_combo = QComboBox()
        self.refresh_ports_button = QPushButton("Rafraîchir")
        self.refresh_ports_button.clicked.connect(self.refresh_serial_ports)
        self.connect_button = QPushButton("Connecter")
        self.connect_button.clicked.connect(self.toggle_connection)
        
        serial_layout.addWidget(QLabel("Port:"), 0, 0)
        serial_layout.addWidget(self.port_combo, 0, 1)
        serial_layout.addWidget(self.refresh_ports_button, 0, 2)
        serial_layout.addWidget(self.connect_button, 1, 0, 1, 3)
        
        # Groupe pour les paramètres d'acquisition
        acquisition_group = QGroupBox("Paramètres d'acquisition")
        acquisition_layout = QGridLayout(acquisition_group)
        
        self.sample_rate_spin = QSpinBox()
        self.sample_rate_spin.setRange(10, 1000)
        self.sample_rate_spin.setValue(self.sample_rate)
        self.sample_rate_spin.setSuffix(" Hz")
        self.sample_rate_spin.valueChanged.connect(self.update_sample_rate)
        
        self.capture_duration_spin = QDoubleSpinBox()
        self.capture_duration_spin.setRange(0.1, 60.0)
        self.capture_duration_spin.setValue(self.capture_duration)
        self.capture_duration_spin.setSuffix(" s")
        self.capture_duration_spin.valueChanged.connect(self.update_capture_duration)
        
        acquisition_layout.addWidget(QLabel("Taux d'échantillonnage:"), 0, 0)
        acquisition_layout.addWidget(self.sample_rate_spin, 0, 1)
        acquisition_layout.addWidget(QLabel("Durée de capture:"), 1, 0)
        acquisition_layout.addWidget(self.capture_duration_spin, 1, 1)
        
        # Groupe pour les contrôles d'affichage
        display_group = QGroupBox("Contrôles d'affichage")
        display_layout = QGridLayout(display_group)
        
        self.real_time_check = QCheckBox("Temps réel")
        self.real_time_check.setChecked(self.is_real_time)
        self.real_time_check.stateChanged.connect(self.toggle_real_time)
        
        self.capture_button = QPushButton("Capturer")
        self.capture_button.clicked.connect(self.toggle_capture)
        self.capture_button.setEnabled(False)
        
        self.save_button = QPushButton("Enregistrer")
        self.save_button.clicked.connect(self.save_data)
        self.save_button.setEnabled(False)
        
        self.clear_button = QPushButton("Effacer")
        self.clear_button.clicked.connect(self.clear_data)
        
        self.export_image_button = QPushButton("Capturer Image")
        self.export_image_button.clicked.connect(self.export_image)
        
        display_layout.addWidget(self.real_time_check, 0, 0)
        display_layout.addWidget(self.capture_button, 0, 1)
        display_layout.addWidget(self.save_button, 1, 0)
        display_layout.addWidget(self.clear_button, 1, 1)
        display_layout.addWidget(self.export_image_button, 2, 0, 1, 2)
        
        # Ajout des groupes au panneau de contrôle
        control_layout.addWidget(serial_group)
        control_layout.addWidget(acquisition_group)
        control_layout.addWidget(display_group)
        
        # Graphique
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setLabel('left', 'Amplitude')
        self.plot_widget.setLabel('bottom', 'Temps', 's')
        self.plot_widget.showGrid(x=True, y=True)
        
        # Courbe pour l'affichage en temps réel
        self.real_time_curve = self.plot_widget.plot(pen=pg.mkPen(color='b', width=2))
        
        # Courbe pour l'affichage des captures
        self.capture_curve = self.plot_widget.plot(pen=pg.mkPen(color='r', width=2))
        
        # Ajout des éléments au layout principal
        main_layout.addWidget(control_panel)
        main_layout.addWidget(self.plot_widget)
        
        # Initialisation des ports série
        self.refresh_serial_ports()
    
    def refresh_serial_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(port.device)
    
    def toggle_connection(self):
        if not self.is_connected:
            try:
                port = self.port_combo.currentText()
                if not port:
                    QMessageBox.warning(self, "Erreur", "Aucun port série sélectionné")
                    return
                
                self.serial_port = serial.Serial(port, 9600, timeout=0.1)
                self.is_connected = True
                self.connect_button.setText("Déconnecter")
                self.capture_button.setEnabled(True)
                self.port_combo.setEnabled(False)
                self.refresh_ports_button.setEnabled(False)
            except Exception as e:
                QMessageBox.critical(self, "Erreur de connexion", f"Impossible de se connecter au port série: {str(e)}")
        else:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            self.is_connected = False
            self.connect_button.setText("Connecter")
            self.capture_button.setEnabled(False)
            self.port_combo.setEnabled(True)
            self.refresh_ports_button.setEnabled(True)
            if self.is_capturing:
                self.toggle_capture()
    
    def update_sample_rate(self, value):
        self.sample_rate = value
    
    def update_capture_duration(self, value):
        self.capture_duration = value
    
    def toggle_real_time(self, state):
        self.is_real_time = (state == Qt.Checked)
    
    def toggle_capture(self):
        if not self.is_capturing:
            self.is_capturing = True
            self.capture_button.setText("Arrêter")
            self.save_button.setEnabled(False)
            self.capture_data = []
            self.capture_start_time = time.time()
            # Afficher un message informatif sur la capture
            QMessageBox.information(self, "Capture en cours", 
                                   f"La capture des données se fera en CSV sur une durée de {self.capture_duration} secondes.\n\n"
                                   f"Les données seront disponibles pour enregistrement une fois la capture terminée.")
        else:
            self.is_capturing = False
            self.capture_button.setText("Capturer")
            self.save_button.setEnabled(True)
    
    def read_serial_data(self):
        if not self.is_connected or not self.serial_port:
            return
        
        try:
            if self.serial_port.in_waiting > 0:
                # Lecture d'une ligne de données
                line = self.serial_port.readline().decode('utf-8').strip()
                
                # Conversion en valeur numérique (supposant que les données sont des nombres)
                try:
                    value = float(line)
                    current_time = time.time()
                    
                    # Ajout aux données en temps réel
                    if len(self.real_time_data) >= self.max_data_points:
                        self.real_time_data.pop(0)
                    self.real_time_data.append((current_time, value))
                    
                    # Ajout aux données de capture si en mode capture
                    if self.is_capturing:
                        elapsed_time = current_time - self.capture_start_time
                        if elapsed_time <= self.capture_duration:
                            self.capture_data.append((elapsed_time, value))
                        else:
                            self.toggle_capture()  # Arrêt automatique après la durée spécifiée
                except ValueError:
                    pass  # Ignorer les lignes qui ne sont pas des nombres
        except Exception as e:
            print(f"Erreur de lecture série: {str(e)}")
            self.toggle_connection()  # Déconnexion en cas d'erreur
    
    def update_plot(self):
        # Mise à jour de la courbe en temps réel
        if self.is_real_time and self.real_time_data:
            x_data = []
            y_data = []
            
            # Calculer le temps relatif par rapport au dernier point
            if len(self.real_time_data) > 0:
                reference_time = self.real_time_data[-1][0]
                for t, v in self.real_time_data:
                    x_data.append(t - reference_time)
                    y_data.append(v)
            
            # Inverser les axes pour que le temps s'écoule de gauche à droite
            x_data = [-x for x in x_data]
            
            self.real_time_curve.setData(x_data, y_data)
            self.capture_curve.setData([], [])
        
        # Affichage des données capturées
        elif not self.is_real_time and self.capture_data:
            x_data = [t for t, v in self.capture_data]
            y_data = [v for t, v in self.capture_data]
            self.capture_curve.setData(x_data, y_data)
            self.real_time_curve.setData([], [])
    
    def clear_data(self):
        # Fonction pour effacer les données affichées
        self.real_time_data = []
        self.capture_data = []
        self.real_time_curve.setData([], [])
        self.capture_curve.setData([], [])
        self.save_button.setEnabled(False)
    
    def save_data(self):
        if not self.capture_data:
            QMessageBox.warning(self, "Avertissement", "Aucune donnée à enregistrer")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Enregistrer les données", "", "Fichiers CSV (*.csv)")
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write("Temps (s),Valeur\n")
                    for t, v in self.capture_data:
                        f.write(f"{t:.6f},{v:.6f}\n")
                QMessageBox.information(self, "Succès", "Données enregistrées avec succès")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de l'enregistrement: {str(e)}")
    
    def export_image(self):
        # Fonction pour exporter l'image du graphique avec les axes de référence
        file_path, _ = QFileDialog.getSaveFileName(self, "Enregistrer l'image", "", "Images PNG (*.png);;Images JPG (*.jpg)")
        if file_path:
            try:
                # Exporter l'image avec les axes et la grille
                exporter = pg.exporters.ImageExporter(self.plot_widget.plotItem)
                exporter.parameters()["antialias"] = True  # Activer l'antialiasing pour une meilleure qualité
                exporter.export(file_path)
                QMessageBox.information(self, "Succès", "Image enregistrée avec succès")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de l'enregistrement de l'image: {str(e)}")

# Point d'entrée principal pour l'application
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OscilloscopeApp()
    window.show()
    sys.exit(app.exec_())