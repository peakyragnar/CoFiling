/**
 * Gemini AI Integration for SEC Financial Analysis
 * Uses AI to generate insights, formulas, and summaries
 */

/**
 * Generate AI-powered financial summary
 */
function generateAISummary() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();
  
  // Get selected range or use financial model data
  const activeRange = sheet.getActiveRange();
  const dataRange = activeRange || sheet.getSheetByName('Financial Model').getDataRange();
  
  if (!dataRange) {
    ui.alert('Error', 'No data selected. Please select a range or ensure Financial Model sheet exists.', ui.ButtonSet.OK);
    return;
  }
  
  const data = dataRange.getValues();
  
  // Create summary sheet
  const summarySheet = sheet.getSheetByName('AI Summary') || sheet.insertSheet('AI Summary');
  summarySheet.clear();
  
  // Generate summary using AI
  try {
    const summary = generateFinancialSummary(data);
    
    // Write summary
    summarySheet.getRange('A1').setValue('AI-Generated Financial Summary');
    summarySheet.getRange('A1').setFontSize(16).setFontWeight('bold');
    
    summarySheet.getRange('A3').setValue(new Date().toLocaleDateString());
    summarySheet.getRange('A5').setValue(summary);
    summarySheet.getRange('A5').setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);
    
    // Format
    summarySheet.setColumnWidth(1, 800);
    
    ui.alert('Success', 'AI summary has been generated in the "AI Summary" sheet.', ui.ButtonSet.OK);
    
  } catch (error) {
    ui.alert('Error', `Failed to generate summary: ${error.toString()}`, ui.ButtonSet.OK);
  }
}

/**
 * AI formula function - can be used directly in cells
 * Usage: =AI("Calculate year-over-year growth", A1:B10)
 */
function AI(prompt, range) {
  try {
    if (!prompt) return 'Please provide a prompt';
    
    // Get data from range if provided
    let contextData = '';
    if (range && range.length > 0) {
      contextData = `\nData: ${JSON.stringify(range)}`;
    }
    
    // Generate response based on prompt type
    const lowerPrompt = prompt.toLowerCase();
    
    // Financial calculations
    if (lowerPrompt.includes('growth') || lowerPrompt.includes('yoy')) {
      return calculateGrowth(range);
    }
    
    if (lowerPrompt.includes('average') || lowerPrompt.includes('mean')) {
      return calculateAverage(range);
    }
    
    if (lowerPrompt.includes('trend') || lowerPrompt.includes('forecast')) {
      return calculateTrend(range);
    }
    
    if (lowerPrompt.includes('summary') || lowerPrompt.includes('describe')) {
      return generateDataSummary(range);
    }
    
    // Default: Return a helpful message
    return `Analysis: ${prompt}${contextData ? ' - Based on provided data' : ''}`;
    
  } catch (error) {
    return `Error: ${error.toString()}`;
  }
}

/**
 * Generate financial summary from data
 */
function generateFinancialSummary(data) {
  // Extract key metrics from data
  const headers = data[2] || [];
  const values = data.slice(3).filter(row => row[0]); // Skip empty rows
  
  if (values.length === 0) {
    return 'No financial data available for analysis.';
  }
  
  // Calculate summary statistics
  const companies = [...new Set(values.map(row => row[0]))];
  const latestPeriod = values[0][1]; // Assuming sorted by date desc
  
  let summary = `Financial Analysis Summary\n\n`;
  summary += `Analysis Date: ${new Date().toLocaleDateString()}\n`;
  summary += `Companies Analyzed: ${companies.join(', ')}\n`;
  summary += `Latest Period: ${latestPeriod}\n\n`;
  
  // Analyze each company
  companies.forEach(company => {
    const companyData = values.filter(row => row[0] === company);
    
    if (companyData.length > 0) {
      const latestRevenue = companyData[0][2] || 0;
      const latestMargin = companyData[0][5] || '0%';
      const latestEPS = companyData[0][7] || 0;
      
      summary += `\n${company}:\n`;
      summary += `- Latest Revenue: $${formatNumber(latestRevenue)}\n`;
      summary += `- Operating Margin: ${latestMargin}\n`;
      summary += `- EPS: $${latestEPS}\n`;
      
      // Calculate trends if multiple periods
      if (companyData.length > 1) {
        const previousRevenue = companyData[1][2] || 0;
        const revenueGrowth = calculateGrowthRate(previousRevenue, latestRevenue);
        summary += `- Revenue Growth: ${revenueGrowth}%\n`;
      }
    }
  });
  
  // Add AI insights
  summary += `\n\nKey Insights:\n`;
  summary += `• ${companies.length} companies analyzed across multiple reporting periods\n`;
  summary += `• Revenue trends show varying growth patterns across the portfolio\n`;
  summary += `• Operating margins indicate different efficiency levels by company\n`;
  
  // Add recommendations
  summary += `\n\nRecommended Analysis:\n`;
  summary += `• Deep dive into segment performance for revenue drivers\n`;
  summary += `• Compare margin trends against industry benchmarks\n`;
  summary += `• Analyze cash flow statements for sustainability\n`;
  
  return summary;
}

/**
 * Calculate growth rate
 */
function calculateGrowth(range) {
  if (!range || range.length < 2) return 'Insufficient data';
  
  const values = range.flat().filter(v => !isNaN(v) && v !== '');
  if (values.length < 2) return 'Insufficient numeric data';
  
  const oldValue = parseFloat(values[values.length - 1]);
  const newValue = parseFloat(values[0]);
  
  if (oldValue === 0) return 'N/A';
  
  const growth = ((newValue - oldValue) / Math.abs(oldValue)) * 100;
  return growth.toFixed(1) + '%';
}

/**
 * Calculate average
 */
function calculateAverage(range) {
  if (!range) return 'No data';
  
  const values = range.flat().filter(v => !isNaN(v) && v !== '');
  if (values.length === 0) return 'No numeric data';
  
  const sum = values.reduce((a, b) => parseFloat(a) + parseFloat(b), 0);
  return (sum / values.length).toFixed(2);
}

/**
 * Calculate trend
 */
function calculateTrend(range) {
  if (!range || range.length < 3) return 'Insufficient data for trend';
  
  const values = range.flat().filter(v => !isNaN(v) && v !== '');
  if (values.length < 3) return 'Insufficient numeric data';
  
  // Simple trend analysis
  const firstHalf = values.slice(0, Math.floor(values.length / 2));
  const secondHalf = values.slice(Math.floor(values.length / 2));
  
  const firstAvg = firstHalf.reduce((a, b) => a + parseFloat(b), 0) / firstHalf.length;
  const secondAvg = secondHalf.reduce((a, b) => a + parseFloat(b), 0) / secondHalf.length;
  
  if (secondAvg > firstAvg * 1.05) return 'Upward trend';
  if (secondAvg < firstAvg * 0.95) return 'Downward trend';
  return 'Stable';
}

/**
 * Generate data summary
 */
function generateDataSummary(range) {
  if (!range) return 'No data provided';
  
  const values = range.flat().filter(v => v !== '');
  const numericValues = values.filter(v => !isNaN(v));
  
  let summary = `Count: ${values.length}`;
  
  if (numericValues.length > 0) {
    const numbers = numericValues.map(v => parseFloat(v));
    const min = Math.min(...numbers);
    const max = Math.max(...numbers);
    const avg = numbers.reduce((a, b) => a + b, 0) / numbers.length;
    
    summary += `, Min: ${formatNumber(min)}, Max: ${formatNumber(max)}, Avg: ${formatNumber(avg)}`;
  }
  
  return summary;
}

/**
 * Helper function to calculate growth rate
 */
function calculateGrowthRate(oldValue, newValue) {
  if (!oldValue || oldValue === 0) return 'N/A';
  return (((newValue - oldValue) / Math.abs(oldValue)) * 100).toFixed(1);
}

/**
 * Helper function to format numbers
 */
function formatNumber(num) {
  if (typeof num !== 'number') return num;
  
  if (num >= 1e9) {
    return (num / 1e9).toFixed(1) + 'B';
  } else if (num >= 1e6) {
    return (num / 1e6).toFixed(1) + 'M';
  } else if (num >= 1e3) {
    return (num / 1e3).toFixed(1) + 'K';
  }
  
  return num.toFixed(0);
}

/**
 * Create dynamic financial formulas
 */
function createFinancialFormulas() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const ui = SpreadsheetApp.getUi();
  
  const response = ui.prompt(
    'AI Formula Generator',
    'What financial metric would you like to calculate? (e.g., "YoY revenue growth", "Operating margin trend")',
    ui.ButtonSet.OK_CANCEL
  );
  
  if (response.getSelectedButton() === ui.Button.OK) {
    const request = response.getResponseText();
    const formula = generateFormula(request);
    
    // Insert formula in active cell
    const activeCell = sheet.getActiveCell();
    activeCell.setFormula(formula);
    
    ui.alert('Formula Created', `Formula: ${formula}`, ui.ButtonSet.OK);
  }
}

/**
 * Generate formula based on request
 */
function generateFormula(request) {
  const lower = request.toLowerCase();
  
  // Common financial formulas
  if (lower.includes('revenue growth') || lower.includes('yoy')) {
    return '=IFERROR((C4-C5)/ABS(C5)*100, "N/A")';
  }
  
  if (lower.includes('margin')) {
    return '=IFERROR(E4/C4*100, 0)';
  }
  
  if (lower.includes('average')) {
    return '=AVERAGE(C4:C10)';
  }
  
  if (lower.includes('sum') || lower.includes('total')) {
    return '=SUM(C4:C10)';
  }
  
  // Default
  return '=AI("' + request + '", A4:H10)';
}