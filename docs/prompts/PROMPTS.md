# PROMPTS — Guía de prompts para agentes IA de SMC-SYSTEMS

**Propósito:** Dar a los agentes de IA (Hermes, subagentes, futuros colaboradores
automatizados) el contexto y las reglas de interacción correctas para extender
este proyecto SIN romper lo existente y SIN inventar.

> Regla de oro: **lee README.md y COMPLETION_REPORT.md antes de tomar
> decisiones técnicas** (AGENTS.md). Aquí se refuerza y se dan plantillas.

---

## 1. Contexto que TODO agente debe tener

- **Modo actual:** observador FundedNext (SIN bot). El loop analiza 24/7; el
  vigilante solo cierra. NO activar ejecución en vivo sin orden de Ruben.
- **Idioma:** español. Responder en español.
- **Restricciones duras:** NO pip-install ni venv sin autorización; NO ejecutar
  launchers pesados (Ruben los corre con doble-clic); NO usar credenciales.
- **Fuente de verdad de hitos:** `docs/CRONOGRAMA_Y_ROADMAP.md`.

---

## 2. Plantillas de prompt por tarea

### 2.1 Extender `ict_backtest/`
```
Contexto: SMC-SYSTEMS / ict_backtest/ (backtest ICT sin ML).
Lee primero: docs/ict/SDD_ICT_BACKTEST.md, docs/ict/API_SPEC.md,
             ict_backtest/market_structure.py, ict_backtest/engine.py.
Tarea: <descripción>.
Reglas: sin look-ahead (ventana no centrada + shift), costos explícitos en
        simulate_trade, walk-forward multi-fold en optimize.py.
Entrega: código + test en tests/test_ict_backtest.py + avance en
         docs/AVANCES_ICT_BACKTEST_*.md. NO commitear sin revisión de Ruben.
```

### 2.2 Auditar / verificar calidad
```
Verifica contra el código REAL (no asumas). Corre los tests:
  pytest tests/test_ict_backtest.py -v
Para cada hallazgo: prueba empírica (serie sintética o datos reales) antes de
reportarlo. Documenta en docs/ict/10_AUDITORIA_REFACCION/ como libro.
```

### 2.3 Documentar una regla ICT
```
Crea un libro en docs/ict/NN_TEMA/ (carpeta=libro, archivos=temas).
Cita fuentes públicas (innercircletrader.net, fluxcharts.com, etc.).
Luego verifica que el detector correspondiente exista y tenga test.
```

### 2.4 Investigar antes de implementar
```
Si la tarea requiere conocimiento externo: busca en internet PRIMERO,
documenta en la biblioteca docs/ict/, crea un libro como es costumbre.
Solo entonces implementas.
```

---

## 3. Anti-patrones prohibidos
- ❌ Inventar funciones/símbolos que no existan en el repo.
- ❌ Asumir que el PF alto en in-sample = edge (requiere OOS multi-fold).
- ❌ Reportar PF sin costos de mercado.
- ❌ Look-ahead en variables derivadas.
- ❌ Borrar módulos sueltos de la raíz (usar `git mv` a legacy/).
- ❌ Commitear sin dejar los cambios para revisión de Ruben.

---

## 4. Formato de entrega esperado
- Código aplicado con `patch`/`write_file` (no solo mostrado en chat).
- Test que pase (`pytest`).
- Avance en `docs/AVANCES_*.md`.
- Commit con mensaje tipo Conventional Commits (`feat:`, `fix:`, `refactor:`,
  `docs:`). Push solo si Ruben lo autoriza.

---

## 5. Referencias rápidas
- `AGENTS.md` — reglas de operación autónoma.
- `docs/DOCUMENTATION_INDEX.md` — mapa de toda la doc.
- `docs/VISION.md`, `PRD.md`, `SRS.md`, `SAD.md` — base del proyecto.
- `docs/ict/00_INDICE.md` — biblioteca ICT.
