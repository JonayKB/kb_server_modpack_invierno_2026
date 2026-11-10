ServerEvents.recipes(event => {
  // Remove as receitas dos cristais do Gobbos
  event.remove({ output: 'gobbos_simple_health_crystals:heart_crystal' })
  event.remove({ output: 'gobbos_simple_health_crystals:blazing_heart_crystal' })
  event.remove({ output: 'gobbos_simple_health_crystals:ender_heart_crystal' })

  // Remove TODAS as receitas do mod More Curios Slots de uma vez só
  event.remove({ mod: 'more_curios_slots' })
})