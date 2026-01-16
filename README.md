
# PYRPHOROS: Gestión de placas solares en entornos Smart Home

Repositorio con los archivos de la maqueta desplegada para el proyecto final de la asignatura Gestión y Administración de Redes de la Universidad de Alcalá.




## Modo de uso

Clonar el repositorio, y configurar los archivos desde el directorio raiz del mismo. Configurar el **hosts.ini** con las configuraciones que creas más oportunas, y lanzar los playbook mediante Ansible.


## Datos Técnicos

Se definen los siguientes playbooks:

-   **pvlib-playbook.yml**: Despliegue de aplicación simulador de placa solar, e instalación de agente SNMPv3 y agente recolector Telegraf.
-   **medium-playbook.yml**: Despliegue de software regional que recolecta datos mediante Telegraf y almacena por medio de InfluxDBv2.
-   **grafana-playbook.yml**: Despliegue de software de monitorización que consulta métricas almacenadas en InfluxDB mediante Grafana.
-   **af-deploy.yml**: Despliegue de una función de aplicación que recolecta direcciones API de las placas solares y traduce a dialogo Diameter para conexión con el HSS local
-   **diameter-deploy.yml**: Despliegue de una base de datos HSS mediante Open5gs + MongoDB para recolección de los datos del AF mediante dialogo Diameter.

A su vez se generan dos scrpits Python:
-   **app/main.py**: Script Python para cálculo de métricas del panel solar en base a la API OpenMeteo, y recolección de los mismos a través de un API Flask.
-   **diameter-agent/gateway_template.py.j2**: Plantilla Jinja2 que genera un script Python que recolecta los datos de las API Flask generadas por medio del inventario y traduce a dialogo Diameter mediante parseo.

## IMPORTANTE

Esta maqueta se ha desplegado en Google Cloud Services en equipos con sistema operativo Debian 12 Bookworm Edition. El despliegue correcto en otro sistema operativo no se garantiza.

Indicar también que distintas claves de servicios han sido usadas y pueden rotar. Si se detecta fallo, solo intercambiar por la clave actual.
