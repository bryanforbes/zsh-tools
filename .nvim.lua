vim.opt.exrc = false

vim.lsp.config('basedpyright', {
  settings = {
    basedpyright = {
      disableOrganizeImports = true,
      analysis = {
        diagnosticMode = 'workspace',
      },
    },
  },
})

require('conform').formatters_by_ft.markdown = { 'prettier' }
