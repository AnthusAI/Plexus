'use client';

import { useTranslationContext } from '@/app/contexts/TranslationContext'

export default function AddEditScorePage() {
  const { locale } = useTranslationContext();
  
  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <h1 className="text-4xl font-bold mb-4">Agregar/Editar una Puntuación</h1>
        <p className="text-lg text-muted-foreground mb-8">
          Aprende cómo crear y gestionar puntuaciones individuales dentro de cuadros de puntuación usando la interfaz del dashboard de Plexus.
        </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Agregar Puntuaciones en el Dashboard</h2>
          <p className="text-muted-foreground mb-4">
            Las puntuaciones son criterios de evaluación individuales dentro de un cuadro de puntuación. El dashboard proporciona
            una interfaz intuitiva para crear y configurar puntuaciones.
          </p>
          
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-3">Guía Paso a Paso</h3>
              <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong>Acceder a la Creación de Puntuaciones:</strong>
                  <p>Abre tu cuadro de puntuación y haz clic en "Agregar Puntuación" o edita un cuadro de puntuación existente.</p>
                </li>
                <li>
                  <strong>Elegir Tipo de Puntuación:</strong>
                  <p>Selecciona entre los tipos de puntuación disponibles:</p>
                  <ul className="list-disc pl-6 mt-2 space-y-2">
                    <li>Análisis de Sentimientos</li>
                    <li>Calidad de Contenido</li>
                    <li>Verificación Gramatical</li>
                    <li>Métricas Personalizadas</li>
                  </ul>
                </li>
                <li>
                  <strong>Configurar Parámetros:</strong>
                  <p>Configura la puntuación:</p>
                  <ul className="list-disc pl-6 mt-2 space-y-2">
                    <li>Nombre y descripción de la puntuación</li>
                    <li>Peso (importancia en el cuadro de puntuación general)</li>
                    <li>Umbral (puntuación mínima aceptable)</li>
                    <li>Parámetros personalizados específicos al tipo de puntuación</li>
                  </ul>
                </li>
                <li>
                  <strong>Vista Previa y Prueba:</strong>
                  <p>Usa la función de vista previa para probar la puntuación contra contenido de muestra.</p>
                </li>
                <li>
                  <strong>Guardar Puntuación:</strong>
                  <p>Haz clic en "Agregar Puntuación" para incluirla en tu cuadro de puntuación.</p>
                </li>
              </ol>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">Editar Puntuaciones Existentes</h3>
              <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong>Localizar la Puntuación:</strong>
                  <p>Encuentra la puntuación que deseas modificar dentro de tu cuadro de puntuación.</p>
                </li>
                <li>
                  <strong>Acceder al Modo de Edición:</strong>
                  <p>Haz clic en el ícono de edición junto a la puntuación.</p>
                </li>
                <li>
                  <strong>Modificar Configuraciones:</strong>
                  <p>Actualiza la configuración de la puntuación según sea necesario.</p>
                </li>
                <li>
                  <strong>Guardar Cambios:</strong>
                  <p>Haz clic en "Guardar" para aplicar tus modificaciones.</p>
                </li>
              </ol>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Gestión de Versiones de Puntuaciones</h2>
          <p className="text-muted-foreground mb-4">
            Las puntuaciones en Plexus soportan versionado, permitiéndote rastrear cambios y gestionar diferentes implementaciones:
          </p>
          
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Crear Nuevas Versiones</h3>
              <p className="text-muted-foreground">
                Cuando editas una puntuación y guardas cambios, se crea automáticamente una nueva versión. 
                Puedes agregar notas para documentar los cambios realizados en cada versión.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Versiones Campeón</h3>
              <p className="text-muted-foreground">
                Cada puntuación tiene una versión "campeón" designada que se usa para evaluaciones.
                Puedes promover cualquier versión a estado campeón cuando estés satisfecho con su rendimiento.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Versiones Destacadas</h3>
              <p className="text-muted-foreground">
                Marca versiones importantes como "destacadas" para resaltarlas en el historial de versiones.
                Esto ayuda a rastrear hitos significativos en el desarrollo de tu puntuación.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Consejos de Configuración de Puntuaciones</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Balance de Pesos</h3>
              <p className="text-muted-foreground">
                Considera cuidadosamente la importancia relativa de cada puntuación al establecer pesos.
                El total de todos los pesos en un cuadro de puntuación debe ser igual a 1.0.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Establecimiento de Umbrales</h3>
              <p className="text-muted-foreground">
                Establece umbrales apropiados basados en tus requisitos de calidad y prueba
                con muestras de contenido representativas.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Tipos de Puntuaciones</h3>
              <p className="text-muted-foreground">
                Elige tipos de puntuación que se alineen con tus objetivos de evaluación. Combina diferentes
                tipos para crear evaluaciones integrales.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Usar la CLI</h2>
          <p className="text-muted-foreground mb-4">
            Para la gestión automatizada de puntuaciones, puedes usar la CLI de Plexus:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`# Ver información detallada sobre una puntuación
plexus scorecards score "Nombre de Puntuación" --account "nombre-cuenta"
plexus scorecards score "clave-puntuacion" --account "nombre-cuenta"

# Mostrar historial de versiones y configuración
plexus scorecards score "Nombre de Puntuación" --account "nombre-cuenta" --show-versions --show-config

# Listar todas las puntuaciones para un cuadro de puntuación específico
plexus scorecards list-scores --scorecard-id "id-cuadro-puntuacion"

# Próximamente:
# Ver historial de versiones para una puntuación
plexus scorecards history --account-key "clave-cuenta" --score-key "clave-puntuacion"

# Promover una versión a campeón
plexus scorecards promote --account-key "clave-cuenta" --score-id "id-puntuacion" --version-id "id-version"

# Agregar una nueva puntuación a un cuadro de puntuación
plexus scores add --scorecard-id "id-cuadro" --name "Puntuación de Calidad" --type quality --weight 0.5

# Listar todas las puntuaciones en un cuadro de puntuación
plexus scores list --scorecard "Aseguramiento de Calidad"

# Ver configuración de puntuación
plexus scores info --score "Verificación Gramatical"`}</code>
          </pre>
          
          <div className="mt-4 space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Búsqueda Eficiente de Puntuaciones</h3>
              <p className="text-muted-foreground">
                El comando <code>score</code> soporta múltiples métodos de búsqueda:
              </p>
              <ul className="list-disc pl-6 mt-2 space-y-2 text-muted-foreground">
                <li>Por ID: <code>plexus scorecards score "id-puntuacion"</code></li>
                <li>Por clave: <code>plexus scorecards score "clave-puntuacion"</code></li>
                <li>Por nombre: <code>plexus scorecards score "Nombre de Puntuación"</code></li>
                <li>Por ID externo: <code>plexus scorecards score "id-externo"</code></li>
              </ul>
              <p className="text-muted-foreground mt-2">
                Puedes limitar la búsqueda a una cuenta específica o cuadro de puntuación para resultados más rápidos.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Referencia del SDK de Python</h2>
          <p className="text-muted-foreground mb-4">
            Para la gestión programática de puntuaciones, puedes usar el SDK de Python:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`from plexus import Plexus

plexus = Plexus(api_key="tu-clave-api")

# Obtener un cuadro de puntuación usando cualquier identificador (nombre, clave, ID, o ID externo)
scorecard = plexus.scorecards.get("Aseguramiento de Calidad")

# Obtener una puntuación usando cualquier identificador
score = plexus.scores.get("Verificación Gramatical")

# Obtener todas las puntuaciones en un cuadro de puntuación
scores = scorecard.get_scores()

# Obtener configuración de puntuación
config = score.get_configuration()

# Obtener resultados de evaluación de puntuación
results = score.get_results(limit=10)`}</code>
          </pre>
          
          <p className="text-muted-foreground mb-4">
            Al igual que la CLI, el SDK de Python también soporta el sistema de identificadores flexible, permitiéndote referenciar recursos usando diferentes tipos de identificadores.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Configuración YAML</h2>
          <p className="text-muted-foreground mb-4">
            Las puntuaciones pueden configurarse usando YAML para personalización avanzada:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`name: Puntuación de Calidad
key: puntuacion-calidad
externalId: score_123
type: LangGraphScore
parameters:
  check_grammar: true
  check_style: true
  min_word_count: 100
threshold: 0.8
weight: 0.5`}</code>
          </pre>
          
          <p className="text-muted-foreground mt-2">
            Próximamente: La capacidad de extraer y subir configuraciones YAML usando la CLI para edición offline y control de versiones.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Próximamente</h2>
          <p className="text-muted-foreground">
            Se están desarrollando características adicionales para puntuaciones. Regresa pronto para:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Nuevos tipos de puntuaciones y métricas</li>
            <li>Algoritmos de puntuación avanzados</li>
            <li>Parámetros de evaluación personalizados</li>
            <li>Analíticas de rendimiento de puntuaciones</li>
            <li>Operaciones masivas de puntuaciones</li>
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
      <h1 className="text-4xl font-bold mb-4">Add/Edit a Score</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn how to create and manage individual scores within scorecards using the Plexus dashboard interface.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Adding Scores in the Dashboard</h2>
          <p className="text-muted-foreground mb-4">
            Scores are individual evaluation criteria within a scorecard. The dashboard provides
            an intuitive interface for creating and configuring scores.
          </p>
          
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-3">Step-by-Step Guide</h3>
              <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong>Access Score Creation:</strong>
                  <p>Open your scorecard and click "Add Score" or edit an existing scorecard.</p>
                </li>
                <li>
                  <strong>Choose Score Type:</strong>
                  <p>Select from available score types:</p>
                  <ul className="list-disc pl-6 mt-2 space-y-2">
                    <li>Sentiment Analysis</li>
                    <li>Content Quality</li>
                    <li>Grammar Check</li>
                    <li>Custom Metrics</li>
                  </ul>
                </li>
                <li>
                  <strong>Configure Parameters:</strong>
                  <p>Set up the score configuration:</p>
                  <ul className="list-disc pl-6 mt-2 space-y-2">
                    <li>Score name and description</li>
                    <li>Weight (importance in overall scorecard)</li>
                    <li>Threshold (minimum acceptable score)</li>
                    <li>Custom parameters specific to the score type</li>
                  </ul>
                </li>
                <li>
                  <strong>Preview and Test:</strong>
                  <p>Use the preview feature to test the score against sample content.</p>
                </li>
                <li>
                  <strong>Save Score:</strong>
                  <p>Click "Add Score" to include it in your scorecard.</p>
                </li>
              </ol>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">Editing Existing Scores</h3>
              <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong>Locate the Score:</strong>
                  <p>Find the score you want to modify within your scorecard.</p>
                </li>
                <li>
                  <strong>Access Edit Mode:</strong>
                  <p>Click the edit icon next to the score.</p>
                </li>
                <li>
                  <strong>Modify Settings:</strong>
                  <p>Update the score's configuration as needed.</p>
                </li>
                <li>
                  <strong>Save Changes:</strong>
                  <p>Click "Save" to apply your modifications.</p>
                </li>
              </ol>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Score Version Management</h2>
          <p className="text-muted-foreground mb-4">
            Scores in Plexus support versioning, allowing you to track changes and manage different implementations:
          </p>
          
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Creating New Versions</h3>
              <p className="text-muted-foreground">
                When you edit a score and save changes, a new version is automatically created. 
                You can add notes to document the changes made in each version.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Champion Versions</h3>
              <p className="text-muted-foreground">
                Each score has a designated "champion" version that is used for evaluations.
                You can promote any version to champion status when you're satisfied with its performance.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Featured Versions</h3>
              <p className="text-muted-foreground">
                Mark important versions as "featured" to highlight them in the version history.
                This helps track significant milestones in your score's development.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Score Configuration Tips</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Weight Balancing</h3>
              <p className="text-muted-foreground">
                Carefully consider the relative importance of each score when setting weights.
                The total of all weights in a scorecard should equal 1.0.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Threshold Setting</h3>
              <p className="text-muted-foreground">
                Set appropriate thresholds based on your quality requirements and test
                with representative content samples.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Score Types</h3>
              <p className="text-muted-foreground">
                Choose score types that align with your evaluation goals. Combine different
                types to create comprehensive assessments.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Using the CLI</h2>
          <p className="text-muted-foreground mb-4">
            For automated score management, you can use the Plexus CLI:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`# View detailed information about a score
plexus scorecards score "Score Name" --account "account-name"
plexus scorecards score "score-key" --account "account-name"

# Show version history and configuration
plexus scorecards score "Score Name" --account "account-name" --show-versions --show-config

# List all scores for a specific scorecard
plexus scorecards list-scores --scorecard-id "scorecard-id"

# Coming soon:
# View version history for a score
plexus scorecards history --account-key "account-key" --score-key "score-key"

# Promote a version to champion
plexus scorecards promote --account-key "account-key" --score-id "score-id" --version-id "version-id"

# Add a new score to a scorecard
plexus scores add --scorecard-id "card-id" --name "Quality Score" --type quality --weight 0.5

# List all scores in a scorecard
plexus scores list --scorecard "Quality Assurance"

# View score configuration
plexus scores info --score "Grammar Check"`}</code>
          </pre>
          
          <div className="mt-4 space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Efficient Score Lookup</h3>
              <p className="text-muted-foreground">
                The <code>score</code> command supports multiple lookup methods:
              </p>
              <ul className="list-disc pl-6 mt-2 space-y-2 text-muted-foreground">
                <li>By ID: <code>plexus scorecards score "score-id"</code></li>
                <li>By key: <code>plexus scorecards score "score-key"</code></li>
                <li>By name: <code>plexus scorecards score "Score Name"</code></li>
                <li>By external ID: <code>plexus scorecards score "external-id"</code></li>
              </ul>
              <p className="text-muted-foreground mt-2">
                You can scope the search to a specific account or scorecard for faster results.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Python SDK Reference</h2>
          <p className="text-muted-foreground mb-4">
            For programmatic score management, you can use the Python SDK:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`from plexus import Plexus

plexus = Plexus(api_key="your-api-key")

# Get a scorecard using any identifier (name, key, ID, or external ID)
scorecard = plexus.scorecards.get("Quality Assurance")

# Get a score using any identifier
score = plexus.scores.get("Grammar Check")

# Get all scores in a scorecard
scores = scorecard.get_scores()

# Get score configuration
config = score.get_configuration()

# Get score evaluation results
results = score.get_results(limit=10)`}</code>
          </pre>
          
          <p className="text-muted-foreground mb-4">
            Like the CLI, the Python SDK also supports the flexible identifier system, allowing you to reference resources using different types of identifiers.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">YAML Configuration</h2>
          <p className="text-muted-foreground mb-4">
            Scores can be configured using YAML for advanced customization:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`name: Quality Score
key: quality-score
externalId: score_123
type: LangGraphScore
parameters:
  check_grammar: true
  check_style: true
  min_word_count: 100
threshold: 0.8
weight: 0.5`}</code>
          </pre>
          
          <p className="text-muted-foreground mt-2">
            Coming soon: The ability to pull and push YAML configurations using the CLI for offline editing and version control.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Additional score features are being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>New score types and metrics</li>
            <li>Advanced scoring algorithms</li>
            <li>Custom evaluation parameters</li>
            <li>Score performance analytics</li>
            <li>Bulk score operations</li>
            <li>YAML synchronization for offline editing</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 