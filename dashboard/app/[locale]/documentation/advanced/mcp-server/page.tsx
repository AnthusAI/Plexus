'use client';

import Link from "next/link";
import { useTranslationContext } from '@/app/contexts/TranslationContext'

export default function McpServerPage() {
  const { locale } = useTranslationContext();
  
  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <style jsx>{`
          .code-container {
            position: relative;
            overflow-x: auto;
            white-space: pre;
            -webkit-overflow-scrolling: touch;
          }
          
          .code-container::after {
            content: '';
            position: absolute;
            right: 0;
            top: 0;
            bottom: 0;
            width: 16px;
            background: linear-gradient(to right, transparent, var(--background-muted));
            opacity: 0;
            transition: opacity 0.2s;
            pointer-events: none;
          }
          
          .code-container:hover::after {
            opacity: 1;
          }
        `}</style>

        <h1 className="text-4xl font-bold mb-4">Usar el Servidor MCP de Plexus</h1>
        <p className="text-lg text-muted-foreground mb-8">
          Conecta asistentes de IA como Claude a tus datos y funcionalidad de Plexus usando el servidor del Protocolo de Contexto de Modelo (MCP).
        </p>

        <div className="space-y-8">
          <section>
            <h2 className="text-2xl font-semibold mb-4">¿Qué es MCP?</h2>
            <p className="text-muted-foreground mb-4">
              El Protocolo de Contexto de Modelo (MCP) es un estándar abierto diseñado por Anthropic que permite a los modelos de IA, como Claude, 
              interactuar de forma segura con herramientas y fuentes de datos externas. Para un asistente de IA, un servidor MCP actúa como una puerta de enlace, 
              permitiéndole acceder y usar capacidades de otros sistemas. En el contexto de Plexus, esto significa que puedes 
              empoderar a una IA para trabajar con tus cuadros de puntuación, evaluaciones y reportes directamente. Esto permite formas más dinámicas y 
              poderosas de interactuar con tu instancia de Plexus. 
              Para una inmersión más profunda en el protocolo mismo, consulta el <Link href="https://www.anthropic.com/news/model-context-protocol" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">anuncio oficial del Protocolo de Contexto de Modelo de Anthropic</Link>.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Resumen del Servidor MCP de Plexus</h2>
            <p className="text-muted-foreground mb-4">
              El servidor MCP de Plexus es una herramienta pre-construida que puedes ejecutar en tu sistema. Una vez ejecutándose, permite a los asistentes de IA 
              que admiten MCP (como la aplicación de escritorio de Claude) conectarse a tu entorno de Plexus. Esta conexión permite a la IA 
              realizar varias acciones dentro de Plexus en tu nombre, como listar cuadros de puntuación, recuperar detalles de reportes, o 
              incluso iniciar nuevas evaluaciones. El servidor típicamente se ejecuta a través de un script wrapper (<code>plexus_fastmcp_wrapper.py</code>) 
              que maneja la configuración del entorno y asegura una comunicación fluida con el cliente de IA.
            </p>
          </section>
          
          <section>
            <h2 className="text-2xl font-semibold mb-4">Obtener el Código del Servidor</h2>
            <p className="text-muted-foreground mb-4">
              Para ejecutar el servidor MCP de Plexus, primero necesitarás obtener el código del servidor. Esto está disponible en el repositorio principal de GitHub de Plexus. 
              Puedes clonarlo o descargarlo desde: <Link href="https://github.com/AnthusAI/Plexus" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">https://github.com/AnthusAI/Plexus</Link>.
              Los scripts necesarios (<code>plexus_fastmcp_wrapper.py</code> y <code>plexus_fastmcp_server.py</code>) están típicamente ubicados en <code>MCP/</code> dentro del repositorio.
              Principalmente necesitarás estos archivos y asegurar que sus dependencias puedan cumplirse en tu entorno de Python.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Configurar un Cliente MCP (ej., Aplicación de Escritorio de Claude)</h2>
            <p className="text-muted-foreground mb-2">
              Para usar el servidor MCP de Plexus, necesitas un cliente MCP. Por ejemplo, si estás usando la aplicación de escritorio de Claude, 
              la configurarías creando o editando un archivo <code>mcp.json</code>. Este archivo le dice a Claude (u otro cliente) 
              cómo encontrar y comunicarse con tu servidor MCP de Plexus en ejecución.
            </p>
            <p className="text-muted-foreground mb-2">
              Aquí hay una configuración de ejemplo para tu archivo <code>mcp.json</code>. Necesitarás reemplazar las rutas de marcador de posición 
              (<code>/path/to/...</code>) con las rutas reales relevantes a tu sistema y donde has clonado el repositorio de Plexus.
            </p>
            <pre className="bg-muted rounded-lg mb-4">
              <div className="code-container p-4">
{`{
  "mcpServers": {
    "plexus-mcp-service": {
      "command": "/path/to/your/conda/envs/py311/bin/python",
      "args": [
        "/path/to/your/Plexus/MCP/plexus_fastmcp_wrapper.py",
        "--host", "127.0.0.1",
        "--port", "8002",
        "--transport", "stdio",
        "--env-file", "/path/to/your/Plexus/.env",
        "--target-cwd", "/path/to/your/Plexus/"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": "/path/to/your/Plexus"
      }
    }
  }
}`}
              </div>
            </pre>
            <p className="text-muted-foreground mb-1">Partes clave de esta configuración:</p>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground mb-4">
              <li><code>command</code>: La ruta completa al intérprete de Python dentro de tu entorno conda de Plexus (ej., <code>py311</code>).</li>
              <li><code>args</code>: Especifica el script wrapper a ejecutar (<code>plexus_fastmcp_wrapper.py</code>) y sus parámetros. 
                  Los argumentos <code>--host</code> y <code>--port</code> configuran los ajustes del servidor local.
                  El argumento <code>--transport stdio</code> es estándar para comunicación cliente-servidor. 
                  El argumento <code>--env-file</code> debe apuntar directamente a tu archivo <code>.env</code> (que contiene claves API). 
                  El <code>--target-cwd</code> debe apuntar a tu directorio raíz del proyecto Plexus.</li>
              <li><code>env.PYTHONPATH</code>: Debe apuntar a la raíz de tu directorio del proyecto Plexus para asegurar que el servidor pueda encontrar todos los módulos de Python necesarios.</li>
            </ul>
            <p className="text-muted-foreground mb-4">
              La ubicación del archivo <code>mcp.json</code> puede variar dependiendo del cliente. Para la aplicación de escritorio de Claude, consulta su documentación para la ubicación correcta (a menudo en un directorio de configuración dentro de tu perfil de usuario).
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Herramientas y Capacidades Disponibles</h2>
            <p className="text-muted-foreground mb-4">Una vez que el servidor MCP de Plexus esté ejecutándose (a través del script wrapper) y tu asistente de IA esté conectado, puedes instruir al asistente para usar las siguientes herramientas:</p>
            
            <div>
              <h3 className="text-xl font-medium mb-2">Gestión de Cuadros de Puntuación</h3>
              <ul className="list-disc pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong><code>list_plexus_scorecards</code></strong>: Pide a la IA que liste los cuadros de puntuación disponibles en tu Dashboard de Plexus. 
                  Opcionalmente puedes decirle que filtre por un nombre/clave de cuenta, un nombre parcial de cuadro de puntuación, o una clave de cuadro de puntuación. Por ejemplo: "Lista los cuadros de puntuación de Plexus para la cuenta 'Ventas' que incluyan 'Q3' en el nombre."
                </li>
                <li>
                  <strong><code>get_plexus_scorecard_info</code></strong>: Solicita información detallada sobre un cuadro de puntuación específico. 
                  Proporciona a la IA un identificador para el cuadro de puntuación (como su nombre, clave, o ID). Devolverá la descripción del cuadro de puntuación, secciones, y las puntuaciones dentro de cada sección. Por ejemplo: "Obtén información para el cuadro de puntuación 'Satisfacción del Cliente Q3'."
                </li>
                <li>
                  <strong><code>get_plexus_score_details</code></strong>: Obtén detalles específicos para una puntuación particular dentro de un cuadro de puntuación, incluyendo su configuración e historial de versiones. 
                  Necesitarás especificar tanto el cuadro de puntuación como la puntuación. También puedes pedir una versión específica de la puntuación. Por ejemplo: "Muéstrame los detalles para la puntuación 'Capacidad de Respuesta' en el cuadro de puntuación 'Tickets de Soporte', especialmente su versión campeón."
                </li>
              </ul>
            </div>

            <div className="mt-6">
              <h3 className="text-xl font-medium mb-2">Herramientas de Evaluación</h3>
              <ul className="list-disc pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong><code>run_plexus_evaluation</code></strong>: Instruye a la IA para iniciar una nueva evaluación de cuadro de puntuación. 
                  Necesitas proporcionar el nombre del cuadro de puntuación y opcionalmente un nombre de puntuación específico y el número de muestras. El servidor enviará esta tarea a tu backend de Plexus. Nota que el servidor MCP en sí no rastrea el progreso; monitorearías la evaluación en el Dashboard de Plexus como siempre. Por ejemplo: "Ejecuta una evaluación de Plexus para el cuadro de puntuación 'Calidad de Leads' usando 100 muestras."
                </li>
              </ul>
            </div>

            <div className="mt-6">
              <h3 className="text-xl font-medium mb-2">Herramientas de Reportes</h3>
              <ul className="list-disc pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong><code>list_plexus_reports</code></strong>: Pide una lista de reportes generados. Puedes filtrar por cuenta o por un ID de configuración de reporte específico si lo conoces. 
                  La IA devolverá una lista mostrando nombres de reportes, IDs, y cuándo fueron creados. Por ejemplo: "Lista los últimos reportes de Plexus para la cuenta principal."
                </li>
                <li>
                  <strong><code>get_plexus_report_details</code></strong>: Recupera información detallada sobre un reporte específico proporcionando su ID. 
                  Esto incluye los parámetros del reporte, salida, y cualquier bloque generado. Por ejemplo: "Obtén los detalles para el reporte de Plexus ID '123-abc-456'."
                </li>
                <li>
                  <strong><code>get_latest_plexus_report</code></strong>: Una forma conveniente de obtener los detalles del reporte generado más recientemente. 
                  Opcionalmente puedes filtrar por cuenta o ID de configuración de reporte. Por ejemplo: "Muéstrame el último reporte generado desde la configuración 'Rendimiento Semanal'."
                </li>
                <li>
                  <strong><code>list_plexus_report_configurations</code></strong>: Obtén una lista de todas las configuraciones de reporte disponibles para una cuenta. 
                  Esto es útil para saber qué reportes *puedes* generar. Por ejemplo: "¿Qué configuraciones de reporte están disponibles para la cuenta 'Marketing'?"
                </li>
              </ul>
            </div>

            <div className="mt-6">
              <h3 className="text-xl font-medium mb-2">Herramientas de Utilidad</h3>
              <ul className="list-disc pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong><code>think</code></strong>: Una herramienta de planificación usada internamente por la IA para estructurar el razonamiento antes de usar otras herramientas.
                  Esto ayuda a la IA a organizar su enfoque para tareas complejas que pueden requerir múltiples pasos o llamadas de herramientas.
                </li>
              </ul>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Requisitos de Entorno para Ejecutar el Servidor</h2>
            <div className="space-y-4">
              <div>
                <h3 className="text-xl font-medium mb-2">Software</h3>
                <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
                  <li>Python 3.11 o más nuevo (requerido por la librería <code>fastmcp</code> que usa el servidor).</li>
                  <li>Una instalación existente de Plexus y acceso a sus credenciales del dashboard.</li>
                  <li>El paquete Python <code>python-dotenv</code> (usado por el servidor para cargar tus claves API desde el archivo <code>.env</code>).</li>
                </ul>
              </div>
              <div>
                <h3 className="text-xl font-medium mb-2">Archivo <code>.env</code> con Credenciales de Plexus</h3>
                <p className="text-muted-foreground mb-2">
                  El servidor necesita acceder a tu API de Plexus. Crea un archivo llamado <code>.env</code>. El parámetro <code>--env-file</code> en tu <code>mcp.json</code> debe apuntar directamente a este archivo.
                  Típicamente se ubica en tu directorio raíz del proyecto Plexus principal (ej., <code>Plexus/.env</code>).
                </p>
                <h4 className="text-lg font-medium mt-2 mb-1">Variables Requeridas en <code>.env</code>:</h4>
                <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
                  <li><code>PLEXUS_API_URL</code>: La URL del endpoint de API para tu instancia de Plexus.</li>
                  <li><code>PLEXUS_API_KEY</code>: Tu clave API para autenticar con Plexus.</li>
                  <li><code>PLEXUS_DASHBOARD_URL</code>: La URL principal de tu dashboard de Plexus (usada para generar enlaces).</li>
                </ul>
                <h4 className="text-lg font-medium mt-2 mb-1">Variables Opcionales en <code>.env</code>:</h4>
                <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
                  <li><code>PLEXUS_ACCOUNT_KEY</code>: Si trabajas con múltiples cuentas, puedes establecer una clave de cuenta predeterminada aquí.</li>
                  <li><code>LOG_LEVEL</code>: Puedes establecer esto a <code>DEBUG</code>, <code>INFO</code>, <code>WARNING</code>, o <code>ERROR</code> para controlar la verbosidad del registro del servidor.</li>
                </ul>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Ejecutar el Servidor</h2>
            <p className="text-muted-foreground mb-2">
              Una vez que tengas el código y tu archivo <code>.env</code> esté configurado, debes ejecutar el servidor usando el script <code>plexus_fastmcp_wrapper.py</code> como se configura en tu archivo <code>mcp.json</code>. 
              El cliente MCP (ej., Aplicación de Escritorio de Claude) ejecutará el comando especificado en <code>mcp.json</code> cuando intente conectarse al "plexus-mcp-service".
            </p>
            <p className="text-muted-foreground mb-2">
              Típicamente no ejecutas el script <code>plexus_fastmcp_wrapper.py</code> manualmente desde la terminal para uso del cliente. En su lugar, asegúrate de que tu <code>mcp.json</code> esté configurado correctamente, y la aplicación cliente iniciará el proceso del servidor según sea necesario.
            </p>
            <p className="text-muted-foreground mb-4">
              Asegúrate de que tu entorno Python de Plexus (ej., <code>conda activate py311</code>) esté correctamente referenciado por la ruta completa a python en el campo <code>command</code> de tu <code>mcp.json</code>. 
              El script wrapper maneja el paso de las variables de entorno y rutas necesarias al <code>plexus_fastmcp_server.py</code> subyacente.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Solución de Problemas Comunes</h2>
            <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
              <li><strong>Errores de Conexión:</strong> Verifica dos veces todas las rutas en tu archivo <code>mcp.json</code> (<code>command</code>, <code>args</code>, <code>env.PYTHONPATH</code>). Asegúrate de que apunten con precisión a tu ejecutable de Python, el script <code>plexus_fastmcp_wrapper.py</code>, tu archivo <code>.env</code>, y tu directorio del proyecto.</li>
              <li><strong>Errores de Autenticación:</strong> Verifica que la ruta <code>--env-file</code> en <code>mcp.json</code> apunte correctamente a tu archivo <code>.env</code> y que este archivo contenga el <code>PLEXUS_API_URL</code> y <code>PLEXUS_API_KEY</code> correctos.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Registros del Servidor</h2>
            <p className="text-muted-foreground mb-2">
              La configuración del servidor MCP de Plexus (a través de <code>plexus_fastmcp_wrapper.py</code>) dirige los registros operacionales y mensajes de error a stderr. 
              Los clientes MCP como la aplicación de escritorio de Claude típicamente capturan y muestran estos registros stderr, o los almacenan en un archivo de registro dedicado.
            </p>
            <p className="text-muted-foreground mb-4">
              Por ejemplo, Cursor a menudo almacena registros de interacción MCP en <code>~/Library/Logs/Claude/mcp.log</code> en macOS. Monitorear este archivo es clave para diagnosticar problemas si el cliente no los muestra directamente.
            </p>
          </section>
        </div>
      </div>
    );
  }
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <style jsx>{`
        .code-container {
          position: relative;
          overflow-x: auto;
          white-space: pre;
          -webkit-overflow-scrolling: touch;
        }
        
        .code-container::after {
          content: '';
          position: absolute;
          right: 0;
          top: 0;
          bottom: 0;
          width: 16px;
          background: linear-gradient(to right, transparent, var(--background-muted));
          opacity: 0;
          transition: opacity 0.2s;
          pointer-events: none;
        }
        
        .code-container:hover::after {
          opacity: 1;
        }
      `}</style>

      <h1 className="text-4xl font-bold mb-4">Using the Plexus MCP Server</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Connect AI assistants like Claude to your Plexus data and functionality using the Model Context Protocol (MCP) server.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">What is MCP?</h2>
          <p className="text-muted-foreground mb-4">
            The Model Context Protocol (MCP) is an open standard designed by Anthropic that allows AI models, such as Claude, 
            to securely interact with external tools and data sources. For an AI assistant, an MCP server acts as a gateway, 
            enabling it to access and use capabilities from other systems. In the context of Plexus, this means you can 
            empower an AI to work with your scorecards, evaluations, and reports directly. This allows for more dynamic and 
            powerful ways to interact with your Plexus instance. 
            For a deeper dive into the protocol itself, see the official <Link href="https://www.anthropic.com/news/model-context-protocol" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">Anthropic Model Context Protocol announcement</Link>.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Plexus MCP Server Overview</h2>
          <p className="text-muted-foreground mb-4">
            The Plexus MCP server is a pre-built tool that you can run on your system. Once running, it allows AI assistants 
            that support MCP (like the Claude desktop app) to connect to your Plexus environment. This connection lets the AI 
            perform various actions within Plexus on your behalf, such as listing scorecards, retrieving report details, or 
            even initiating new evaluations. The server is typically run via a wrapper script (<code>plexus_fastmcp_wrapper.py</code>) 
            which handles environment setup and ensures smooth communication with the AI client.
          </p>
        </section>
        
        <section>
          <h2 className="text-2xl font-semibold mb-4">Getting the Server Code</h2>
          <p className="text-muted-foreground mb-4">
            To run the Plexus MCP server, you'll first need to obtain the server code. This is available in the main Plexus GitHub repository. 
            You can clone or download it from: <Link href="https://github.com/AnthusAI/Plexus" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">https://github.com/AnthusAI/Plexus</Link>.
            The necessary scripts (<code>plexus_fastmcp_wrapper.py</code> and <code>plexus_fastmcp_server.py</code>) are typically located at <code>MCP/</code> within the repository.
            You will primarily need these files and to ensure their dependencies can be met in your Python environment.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Setting Up an MCP Client (e.g., Claude Desktop App)</h2>
          <p className="text-muted-foreground mb-2">
            To use the Plexus MCP server, you need an MCP client. For example, if you are using the Claude desktop application, 
            you would configure it by creating or editing an <code>mcp.json</code> file. This file tells Claude (or another client) 
            how to find and communicate with your running Plexus MCP server.
          </p>
          <p className="text-muted-foreground mb-2">
            Here is an example configuration for your <code>mcp.json</code> file. You will need to replace the placeholder paths 
            (<code>/path/to/...</code>) with the actual paths relevant to your system and where you have cloned the Plexus repository.
          </p>
          <pre className="bg-muted rounded-lg mb-4">
            <div className="code-container p-4">
{`{
  "mcpServers": {
    "plexus-mcp-service": {
      "command": "/path/to/your/conda/envs/py311/bin/python",
      "args": [
        "/path/to/your/Plexus/MCP/plexus_fastmcp_wrapper.py",
        "--host", "127.0.0.1",
        "--port", "8002",
        "--transport", "stdio",
        "--env-file", "/path/to/your/Plexus/.env",
        "--target-cwd", "/path/to/your/Plexus/"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": "/path/to/your/Plexus"
      }
    }
  }
}`}
            </div>
          </pre>
          <p className="text-muted-foreground mb-1">Key parts of this configuration:</p>
          <ul className="list-disc pl-6 space-y-1 text-muted-foreground mb-4">
            <li><code>command</code>: The full path to the Python interpreter within your Plexus conda environment (e.g., <code>py311</code>).</li>
            <li><code>args</code>: Specifies the wrapper script to run (<code>plexus_fastmcp_wrapper.py</code>) and its parameters. 
                The <code>--host</code> and <code>--port</code> arguments configure the local server settings.
                The <code>--transport stdio</code> argument is standard for client-server communication. 
                The <code>--env-file</code> argument must point directly to your <code>.env</code> file (which contains API keys). 
                The <code>--target-cwd</code> should point to your Plexus project root directory.</li>
            <li><code>env.PYTHONPATH</code>: Should point to the root of your Plexus project directory to ensure the server can find all necessary Python modules.</li>
          </ul>
          <p className="text-muted-foreground mb-4">
            The location of the <code>mcp.json</code> file can vary depending on the client. For the Claude desktop app, consult its documentation for the correct location (often in a configuration directory within your user profile).
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Available Tools & Capabilities</h2>
          <p className="text-muted-foreground mb-4">Once the Plexus MCP server is running (via the wrapper script) and your AI assistant is connected, you can instruct the assistant to use the following tools:</p>
          
          <div>
            <h3 className="text-xl font-medium mb-2">Scorecard Management</h3>
            <ul className="list-disc pl-6 space-y-3 text-muted-foreground">
              <li>
                <strong><code>list_plexus_scorecards</code></strong>: Ask the AI to list available scorecards in your Plexus Dashboard. 
                You can optionally tell it to filter by an account name/key, a partial scorecard name, or a scorecard key. For example: "List Plexus scorecards for the 'Sales' account that include 'Q3' in the name."
              </li>
              <li>
                <strong><code>get_plexus_scorecard_info</code></strong>: Request detailed information about a specific scorecard. 
                Provide the AI with an identifier for the scorecard (like its name, key, or ID). It will return the scorecard's description, sections, and the scores within each section. For example: "Get info for the 'Customer Satisfaction Q3' scorecard."
              </li>
              <li>
                <strong><code>get_plexus_score_details</code></strong>: Get specific details for a particular score within a scorecard, including its configuration and version history. 
                You'll need to specify both the scorecard and the score. You can also ask for a specific version of the score. For example: "Show me the details for the 'Responsiveness' score in the 'Support Tickets' scorecard, especially its champion version."
              </li>
            </ul>
          </div>

          <div className="mt-6">
            <h3 className="text-xl font-medium mb-2">Evaluation Tools</h3>
            <ul className="list-disc pl-6 space-y-3 text-muted-foreground">
              <li>
                <strong><code>run_plexus_evaluation</code></strong>: Instruct the AI to start a new scorecard evaluation. 
                You need to provide the scorecard name and optionally a specific score name and the number of samples. The server will dispatch this task to your Plexus backend. Note that the MCP server itself doesn't track the progress; you would monitor the evaluation in the Plexus Dashboard as usual. For example: "Run a Plexus evaluation for the 'Lead Quality' scorecard using 100 samples."
              </li>
            </ul>
          </div>

          <div className="mt-6">
            <h3 className="text-xl font-medium mb-2">Reporting Tools</h3>
            <ul className="list-disc pl-6 space-y-3 text-muted-foreground">
              <li>
                <strong><code>list_plexus_reports</code></strong>: Ask for a list of generated reports. You can filter by account or by a specific report configuration ID if you know it. 
                The AI will return a list showing report names, IDs, and when they were created. For example: "List the latest Plexus reports for the main account."
              </li>
              <li>
                <strong><code>get_plexus_report_details</code></strong>: Retrieve detailed information about a specific report by providing its ID. 
                This includes the report's parameters, output, and any generated blocks. For example: "Get the details for Plexus report ID '123-abc-456'."
              </li>
              <li>
                <strong><code>get_latest_plexus_report</code></strong>: A convenient way to get the details of the most recently generated report. 
                You can optionally filter by account or report configuration ID. For example: "Show me the latest report generated from the 'Weekly Performance' configuration."
              </li>
              <li>
                <strong><code>list_plexus_report_configurations</code></strong>: Get a list of all available report configurations for an account. 
                This is useful for knowing what reports you *can* generate. For example: "What report configurations are available for the 'Marketing' account?"
              </li>
            </ul>
          </div>

          <div className="mt-6">
            <h3 className="text-xl font-medium mb-2">Utility Tools</h3>
            <ul className="list-disc pl-6 space-y-3 text-muted-foreground">
              <li>
                <strong><code>think</code></strong>: A planning tool used internally by the AI to structure reasoning before using other tools.
                This helps the AI organize its approach to complex tasks that may require multiple steps or tool calls.
              </li>
            </ul>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Environment Requirements for Running the Server</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Software</h3>
              <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
                <li>Python 3.11 or newer (required by the <code>fastmcp</code> library the server uses).</li>
                <li>An existing Plexus installation and access to its dashboard credentials.</li>
                <li>The <code>python-dotenv</code> Python package (used by the server to load your API keys from the <code>.env</code> file).</li>
              </ul>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2"><code>.env</code> File with Plexus Credentials</h3>
              <p className="text-muted-foreground mb-2">
                The server needs to access your Plexus API. Create a file named <code>.env</code>. The <code>--env-file</code> parameter in your <code>mcp.json</code> should point directly to this file.
                It's typically located in your main Plexus project root directory (e.g., <code>Plexus/.env</code>).
              </p>
              <h4 className="text-lg font-medium mt-2 mb-1">Required Variables in <code>.env</code>:</h4>
              <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
                <li><code>PLEXUS_API_URL</code>: The API endpoint URL for your Plexus instance.</li>
                <li><code>PLEXUS_API_KEY</code>: Your API key for authenticating with Plexus.</li>
                <li><code>PLEXUS_DASHBOARD_URL</code>: The main URL of your Plexus dashboard (used for generating links).</li>
              </ul>
              <h4 className="text-lg font-medium mt-2 mb-1">Optional Variables in <code>.env</code>:</h4>
              <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
                <li><code>PLEXUS_ACCOUNT_KEY</code>: If you work with multiple accounts, you can set a default account key here.</li>
                <li><code>LOG_LEVEL</code>: You can set this to <code>DEBUG</code>, <code>INFO</code>, <code>WARNING</code>, or <code>ERROR</code> to control the server's logging verbosity.</li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Running the Server</h2>
          <p className="text-muted-foreground mb-2">
            Once you have the code and your <code>.env</code> file is set up, you should run the server using the <code>plexus_fastmcp_wrapper.py</code> script as configured in your <code>mcp.json</code> file. 
            The MCP client (e.g., Claude Desktop App) will execute the command specified in <code>mcp.json</code> when it attempts to connect to the "plexus-mcp-service".
          </p>
          <p className="text-muted-foreground mb-2">
            You typically don't run the <code>plexus_fastmcp_wrapper.py</code> script manually from the terminal for client use. Instead, ensure your <code>mcp.json</code> is correctly configured, and the client application will start the server process as needed.
          </p>
          <p className="text-muted-foreground mb-4">
            Make sure your Plexus Python environment (e.g., <code>conda activate py311</code>) is correctly referenced by the full path to python in the <code>command</code> field of your <code>mcp.json</code>. 
            The wrapper script handles passing the necessary environment variables and paths to the underlying <code>plexus_fastmcp_server.py</code>.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Troubleshooting Common Issues</h2>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li><strong>Connection Errors:</strong> Double-check all paths in your <code>mcp.json</code> file (<code>command</code>, <code>args</code>, <code>env.PYTHONPATH</code>). Ensure they accurately point to your Python executable, the <code>plexus_fastmcp_wrapper.py</code> script, your <code>.env</code> file, and your project directory.</li>
            <li><strong>Authentication Errors:</strong> Verify that the <code>--env-file</code> path in <code>mcp.json</code> correctly points to your <code>.env</code> file and that this file contains the correct <code>PLEXUS_API_URL</code> and <code>PLEXUS_API_KEY</code>.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Server Logs</h2>
          <p className="text-muted-foreground mb-2">
            The Plexus MCP server setup (via <code>plexus_fastmcp_wrapper.py</code>) directs operational logs and error messages to stderr. 
            MCP clients like the Claude desktop app typically capture and display these stderr logs, or store them in a dedicated log file.
          </p>
          <p className="text-muted-foreground mb-4">
            For instance, Cursor often stores MCP interaction logs in <code>~/Library/Logs/Claude/mcp.log</code> on macOS. Monitoring this file is key for diagnosing issues if the client doesn't display them directly.
          </p>
        </section>
      </div>
    </div>
  )
} 