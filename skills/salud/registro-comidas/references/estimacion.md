# Estimación de porciones (texto y foto)

Objetivo: cantidades defendibles, declaradas, y preguntar solo cuando el error posible es grande.

## Reglas de decisión

| Situación | Qué hacer |
|---|---|
| El usuario da gramos o una porción clara ("2 huevos", "1 taza de arroz") | Registrar tal cual |
| Porción estándar con poco margen de error (una fruta, un café, una rebanada) | Asumir la porción de la base y declararla |
| Plato de restaurante con nombre conocido | Estimar ración estándar por ingredientes, anotar `--nota`, ofrecer ajuste |
| Cantidad ambigua de algo calórico ("un poco de arroz", "unos trocitos de chancho", "con aceite") | Preguntar antes de registrar |
| Producto con marca | Pedir foto de la etiqueta y usar sus valores con `--manual` |
| La respuesta a una pregunta no llega | Registrar con el valor razonable, declararlo y ofrecer recálculo |

Error típico a evitar: "3 cubitos de pollo" son ≈ 30-40 g cada uno (≈ 100 g en total), no 300 g.

## Equivalencias caseras (aproximadas)

| Referencia | Equivale a |
|---|---|
| Palma de la mano (sin dedos), grosor de un dedo | 90-120 g de carne o pescado cocido |
| Puño cerrado | ≈ 1 taza: 150-180 g de arroz o pasta cocidos |
| Pulgar (punta a base) | ≈ 1 cucharada: 14 g de aceite o mantequilla, 15 g de mayonesa |
| Plato llano (≈ 26 cm) lleno de arroz | 250-300 g cocido |
| Cucharón de guiso o menestra | 150-200 g |
| Puñado de frutos secos | ≈ 28 g |
| Vaso común | 200-250 ml |

## Por dimensiones (cuando el usuario da medidas)

Peso ≈ volumen × densidad. Volúmenes: cilindro π·r²·h, prisma l·a·h, esfera 4/3·π·r³.

| Alimento | Densidad aprox. (g/cm³) |
|---|---|
| Pan (miga) | 0,25-0,40 |
| Embutidos | 0,9-1,2 |
| Carne molida compacta | 1,0-1,1 |
| Quesos | 1,0-1,2 |
| Fruta entera | 0,6-0,8 |
| Tubérculos | 0,65-0,8 |
| Chocolate en barra | 1,1-1,3 |

Ejemplo: salchicha de 3 cm de diámetro × 10 cm → π·1,5²·10 ≈ 71 cm³ × 1,1 ≈ 78 g.
Redondea a cifras limpias (80 g): un decimal de más no da precisión, da falsa precisión.
Si solo hay "como un puño" o "del tamaño de un plato", pide medidas o usa la tabla de equivalencias.

## Fotos

1. **Inventario:** lista cada componente visible (proteína, guarnición, salsa, bebida, extras).
2. **Escala:** busca una referencia en la imagen: plato (llano ≈ 26 cm, de postre ≈ 20 cm), cubiertos
   (tenedor ≈ 19 cm), lata (355 ml), mano, envase con peso impreso.
3. **Porción:** estima área ocupada × altura aparente, o compara con las equivalencias de arriba.
4. **Lo invisible:** aceite de fritura, aderezos, azúcar en bebidas. Si cambia mucho el total, pregunta
   ("¿la ensalada lleva aderezo?"); si no, asume lo habitual y decláralo.
5. **Declara y registra:** "Veo ~200 g de arroz, un filete de ~150 g y ensalada sin aderezo. Lo registro
   así; dime si ajusto."
6. **Etiqueta nutricional en la foto:** lee porción, kcal y macros, y escala a lo consumido. Es el dato
   más confiable que existe: prefiérelo a la base.

Precisión: toda estimación sin balanza tiene margen de error, y por foto más que por descripción.
Por eso se declaran los supuestos y se ofrece ajustar.

## Bebidas alcohólicas

El alcohol aporta ~7 kcal/g y no es proteína, grasa ni carbohidrato: en cerveza y vino, las kcal de la
base son mayores que 4P+4C+9G. El validador lo avisa como "revisa"; es correcto.
