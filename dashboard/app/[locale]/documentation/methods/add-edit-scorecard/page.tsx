'use client';

import { useTranslationContext } from '@/app/contexts/TranslationContext'

export default function AddEditScorecardPage() {
  const { locale } = useTranslationContext();
  
  if (locale === 'es') {
    return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Agregar/Editar un Cuadro de Puntuación</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Aprende cómo crear y administrar cuadros de puntuación usando la interfaz del dashboard de Plexus.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Crear un Cuadro de Puntuación en el Dashboard</h2>
          <p className="text-muted-foreground mb-4">
            Los cuadros de puntuación definen los criterios para evaluar tu contenido. El dashboard proporciona
            una interfaz intuitiva para crear y administrar cuadros de puntuación.
          </p>
          
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-3">Guía Paso a Paso</h3>
              <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong>Acceder a Cuadros de Puntuación:</strong>
                  <p>Navega a la sección "Cuadros de Puntuación" en el menú de navegación principal.</p>
                </li>
                <li>
                  <strong>Crear Nuevo Cuadro de Puntuación:</strong>
                  <p>Haz clic en el botón "Nuevo Cuadro de Puntuación" en la esquina superior derecha.</p>
                </li>
                <li>
                  <strong>Información Básica:</strong>
                  <p>Completa los detalles del cuadro de puntuación:</p>
                  <ul className="list-disc pl-6 mt-2 space-y-2">
                    <li>Nombre del cuadro de puntuación</li>
                    <li>Descripción</li>
                    <li>Categoría/etiquetas (opcional)</li>
                  </ul>
                </li>
                <li>
                  <strong>Agregar Puntuaciones:</strong>
                  <p>Haz clic en "Agregar Puntuación" para incluir criterios de evaluación:</p>
                  <ul className="list-disc pl-6 mt-2 space-y-2">
                    <li>Seleccionar tipo de puntuación</li>
                    <li>Configurar parámetros de puntuación</li>
                    <li>Establecer peso y umbral</li>
                  </ul>
                </li>
                <li>
                  <strong>Guardar Cuadro de Puntuación:</strong>
                  <p>Haz clic en "Crear" para guardar tu nuevo cuadro de puntuación.</p>
                </li>
              </ol>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">Editar un Cuadro de Puntuación</h3>
              <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong>Encontrar el Cuadro de Puntuación:</strong>
                  <p>Localiza el cuadro de puntuación que deseas modificar en la lista de Cuadros de Puntuación.</p>
                </li>
                <li>
                  <strong>Entrar en Modo de Edición:</strong>
                  <p>Haz clic en el ícono de editar o selecciona "Editar" del menú de acciones.</p>
                </li>
                <li>
                  <strong>Realizar Cambios:</strong>
                  <p>Modifica los detalles del cuadro de puntuación, agrega/elimina puntuaciones, o ajusta pesos.</p>
                </li>
                <li>
                  <strong>Guardar Actualizaciones:</strong>
                  <p>Haz clic en "Guardar Cambios" para aplicar tus modificaciones.</p>
                </li>
              </ol>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Consejos para la Gestión de Cuadros de Puntuación</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Organización</h3>
              <p className="text-muted-foreground">
                Usa nombres y descripciones significativos para mantener tus cuadros de puntuación organizados.
                Considera usar etiquetas para agrupar cuadros de puntuación relacionados.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Pesos de Puntuación</h3>
              <p className="text-muted-foreground">
                Equilibra los pesos de las puntuaciones para reflejar la importancia relativa de cada criterio
                en tu proceso de evaluación.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Plantillas</h3>
              <p className="text-muted-foreground">
                Guarda configuraciones de cuadros de puntuación comúnmente utilizadas como plantillas para reutilización rápida.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Usar la CLI</h2>
          <p className="text-muted-foreground mb-4">
            Para la gestión automatizada de cuadros de puntuación, puedes usar la CLI de Plexus:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`# Listar cuadros de puntuación con rendimiento optimizado
plexus scorecards list "account-name" --fast

# Ver un cuadro de puntuación específico por filtrado
plexus scorecards list "account-name" --name "Calidad de Contenido"

# Ver información detallada sobre una puntuación
plexus scorecards score "score-name" --account "account-name" --show-versions

# Próximamente:
# Crear un nuevo cuadro de puntuación
plexus scorecards create --name "Calidad de Contenido" --description "Evalúa la calidad del contenido"

# Obtener información detallada sobre un cuadro de puntuación específico
plexus scorecards info --scorecard "Calidad de Contenido"

# Listar todas las puntuaciones en un cuadro de puntuación
plexus scorecards list-scores --scorecard "Calidad de Contenido"

# Extraer configuración del cuadro de puntuación a YAML
plexus scorecards pull --scorecard "Calidad de Contenido" --output ./mis-cuadros-puntuacion

# Subir configuración del cuadro de puntuación desde YAML
plexus scorecards push --scorecard "Calidad de Contenido" --file ./mi-cuadro-puntuacion.yaml --note "Configuración actualizada"

# Eliminar un cuadro de puntuación
plexus scorecards delete --scorecard "Calidad de Contenido"`}</code>
          </pre>
          
          <div className="mt-4 space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Consideraciones de Rendimiento</h3>
              <p className="text-muted-foreground">
                La CLI ahora usa consultas GraphQL optimizadas para obtener datos de cuadros de puntuación de manera eficiente:
              </p>
              <ul className="list-disc pl-6 mt-2 space-y-2 text-muted-foreground">
                <li>
                  <strong>Enfoque de Consulta Única:</strong> En lugar de hacer consultas separadas para las secciones y puntuaciones de cada cuadro de puntuación, 
                  el sistema ahora obtiene todos los datos en una sola consulta GraphQL comprensiva.
                </li>
                <li>
                  <strong>Modo Rápido:</strong> Usa la opción <code>--fast</code> para omitir la obtención de secciones y puntuaciones cuando solo necesitas información básica del cuadro de puntuación.
                </li>
                <li>
                  <strong>Ocultar Puntuaciones:</strong> Usa <code>--hide-scores</code> para excluir detalles de puntuación de la salida mientras aún obtienes datos básicos del cuadro de puntuación.
                </li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Referencia del SDK de Python</h2>
          <p className="text-muted-foreground mb-4">
            Para la gestión programática de cuadros de puntuación, puedes usar el SDK de Python:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`from plexus import Plexus

plexus = Plexus(api_key="tu-clave-api")

# Obtener un cuadro de puntuación usando cualquier identificador (nombre, clave, ID, o ID externo)
scorecard = plexus.scorecards.get("Calidad de Contenido")

# Listar todos los cuadros de puntuación
scorecards = plexus.scorecards.list()

# Obtener todas las puntuaciones en un cuadro de puntuación
scores = scorecard.get_scores()

# Exportar cuadro de puntuación a YAML
yaml_config = scorecard.to_yaml()
with open("cuadro-puntuacion.yaml", "w") as f:
    f.write(yaml_config)

# Importar cuadro de puntuación desde YAML
with open("cuadro-puntuacion.yaml", "r") as f:
    yaml_content = f.read()
    
nuevo_scorecard = plexus.scorecards.from_yaml(yaml_content)`}</code>
          </pre>
          
          <p className="text-muted-foreground mb-4">
            Al igual que la CLI, el SDK de Python también soporta el sistema de identificadores flexible, permitiéndote referenciar cuadros de puntuación usando diferentes tipos de identificadores.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Próximamente</h2>
          <p className="text-muted-foreground">
            Se están desarrollando características adicionales para cuadros de puntuación. Regresa pronto para:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Opciones avanzadas de configuración de puntuación</li>
            <li>Control de versiones de cuadros de puntuación</li>
            <li>Características de edición colaborativa</li>
            <li>Analíticas de rendimiento</li>
            <li>Sincronización YAML para edición offline</li>
          </ul>
        </section>
      </div>
    </div>
    );
  }

  // English content (default)
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Add/Edit a Scorecard</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn how to create and manage scorecards using the Plexus dashboard interface.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Creating a Scorecard in the Dashboard</h2>
          <p className="text-muted-foreground mb-4">
            Scorecards define the criteria for evaluating your content. The dashboard provides
            an intuitive interface for creating and managing scorecards.
          </p>
          
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-3">Step-by-Step Guide</h3>
              <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong>Access Scorecards:</strong>
                  <p>Navigate to the "Scorecards" section in the main navigation menu.</p>
                </li>
                <li>
                  <strong>Create New Scorecard:</strong>
                  <p>Click the "New Scorecard" button in the top-right corner.</p>
                </li>
                <li>
                  <strong>Basic Information:</strong>
                  <p>Fill in the scorecard details:</p>
                  <ul className="list-disc pl-6 mt-2 space-y-2">
                    <li>Scorecard name</li>
                    <li>Description</li>
                    <li>Category/tags (optional)</li>
                  </ul>
                </li>
                <li>
                  <strong>Add Scores:</strong>
                  <p>Click "Add Score" to include evaluation criteria:</p>
                  <ul className="list-disc pl-6 mt-2 space-y-2">
                    <li>Select score type</li>
                    <li>Configure score parameters</li>
                    <li>Set weight and threshold</li>
                  </ul>
                </li>
                <li>
                  <strong>Save Scorecard:</strong>
                  <p>Click "Create" to save your new scorecard.</p>
                </li>
              </ol>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">Editing a Scorecard</h3>
              <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong>Find the Scorecard:</strong>
                  <p>Locate the scorecard you want to modify in the Scorecards list.</p>
                </li>
                <li>
                  <strong>Enter Edit Mode:</strong>
                  <p>Click the edit icon or select "Edit" from the actions menu.</p>
                </li>
                <li>
                  <strong>Make Changes:</strong>
                  <p>Modify scorecard details, add/remove scores, or adjust weights.</p>
                </li>
                <li>
                  <strong>Save Updates:</strong>
                  <p>Click "Save Changes" to apply your modifications.</p>
                </li>
              </ol>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Scorecard Management Tips</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Organization</h3>
              <p className="text-muted-foreground">
                Use meaningful names and descriptions to keep your scorecards organized.
                Consider using tags to group related scorecards.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Score Weights</h3>
              <p className="text-muted-foreground">
                Balance score weights to reflect the relative importance of each criterion
                in your evaluation process.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Templates</h3>
              <p className="text-muted-foreground">
                Save commonly used scorecard configurations as templates for quick reuse.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Using the CLI</h2>
          <p className="text-muted-foreground mb-4">
            For automated scorecard management, you can use the Plexus CLI:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`# List scorecards with optimized performance
plexus scorecards list "account-name" --fast

# View a specific scorecard by filtering
plexus scorecards list "account-name" --name "Content Quality"

# View detailed information about a score
plexus scorecards score "score-name" --account "account-name" --show-versions

# Coming soon:
# Create a new scorecard
plexus scorecards create --name "Content Quality" --description "Evaluates content quality"

# Get detailed information about a specific scorecard
plexus scorecards info --scorecard "Content Quality"

# List all scores in a scorecard
plexus scorecards list-scores --scorecard "Content Quality"

# Pull scorecard configuration to YAML
plexus scorecards pull --scorecard "Content Quality" --output ./my-scorecards

# Push scorecard configuration from YAML
plexus scorecards push --scorecard "Content Quality" --file ./my-scorecard.yaml --note "Updated configuration"

# Delete a scorecard
plexus scorecards delete --scorecard "Content Quality"`}</code>
          </pre>
          
          <div className="mt-4 space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Performance Considerations</h3>
              <p className="text-muted-foreground">
                The CLI now uses optimized GraphQL queries to efficiently fetch scorecard data:
              </p>
              <ul className="list-disc pl-6 mt-2 space-y-2 text-muted-foreground">
                <li>
                  <strong>Single Query Approach:</strong> Instead of making separate queries for each scorecard's sections and scores, 
                  the system now fetches all data in one comprehensive GraphQL query.
                </li>
                <li>
                  <strong>Fast Mode:</strong> Use the <code>--fast</code> option to skip fetching sections and scores when you only need basic scorecard info.
                </li>
                <li>
                  <strong>Hide Scores:</strong> Use <code>--hide-scores</code> to exclude score details from output while still getting basic scorecard data.
                </li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Python SDK Reference</h2>
          <p className="text-muted-foreground mb-4">
            For programmatic scorecard management, you can use the Python SDK:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`from plexus import Plexus

plexus = Plexus(api_key="your-api-key")

# Get a scorecard using any identifier (name, key, ID, or external ID)
scorecard = plexus.scorecards.get("Content Quality")

# List all scorecards
scorecards = plexus.scorecards.list()

# Get all scores in a scorecard
scores = scorecard.get_scores()

# Export scorecard to YAML
yaml_config = scorecard.to_yaml()
with open("scorecard.yaml", "w") as f:
    f.write(yaml_config)

# Import scorecard from YAML
with open("scorecard.yaml", "r") as f:
    yaml_content = f.read()
    
new_scorecard = plexus.scorecards.from_yaml(yaml_content)`}</code>
          </pre>
          
          <p className="text-muted-foreground mb-4">
            Like the CLI, the Python SDK also supports the flexible identifier system, allowing you to reference scorecards using different types of identifiers.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Additional scorecard features are being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Advanced score configuration options</li>
            <li>Scorecard version control</li>
            <li>Collaborative editing features</li>
            <li>Performance analytics</li>
            <li>YAML synchronization for offline editing</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 