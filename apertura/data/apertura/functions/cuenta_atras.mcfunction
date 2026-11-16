# Inicia la cuenta atras de apertura (10 segundos)
# Uso: /function apertura:cuenta_atras
scoreboard objectives add apertura dummy
scoreboard players set #t apertura 10

title @a times 0 30 10
title @a title {"text":"PREPARADOS","color":"gold","bold":true}
title @a subtitle {"text":"El servidor esta a punto de abrir...","color":"yellow"}
execute as @a at @s run playsound minecraft:block.beacon.activate master @s ~ ~ ~ 1 1

schedule function apertura:tick 3s
