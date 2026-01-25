import { useState, useEffect } from 'react'
import * as api from '../services/api'

/**
 * Hook for managing app configuration state
 */
export function useConfig() {
  const [config, setConfig] = useState({
    assignments_folder: '',
    output_folder: '',
    roster_file: '',
    grading_period: 'Q1',
  })

  const [globalAINotes, setGlobalAINotes] = useState('')
  const [loading, setLoading] = useState(true)

  // Load saved settings on mount
  useEffect(() => {
    async function loadSettings() {
      try {
        const result = await api.loadGlobalSettings()
        if (result.settings) {
          if (result.settings.globalAINotes) {
            setGlobalAINotes(result.settings.globalAINotes)
          }
          if (result.settings.config) {
            setConfig(prev => ({ ...prev, ...result.settings.config }))
          }
        }
      } catch (error) {
        console.error('Failed to load settings:', error)
      } finally {
        setLoading(false)
      }
    }
    loadSettings()
  }, [])

  // Save settings when they change
  const saveSettings = async () => {
    try {
      await api.saveGlobalSettings({
        globalAINotes,
        config,
      })
    } catch (error) {
      console.error('Failed to save settings:', error)
    }
  }

  const updateConfig = (updates) => {
    setConfig(prev => ({ ...prev, ...updates }))
  }

  return {
    config,
    setConfig,
    updateConfig,
    globalAINotes,
    setGlobalAINotes,
    saveSettings,
    loading,
  }
}

export default useConfig
