# Model Comparison Table across Forecast Horizons

Evaluation conducted on untouched chronological test set (last 15% of 60-day historical time series).

## Overall Horizon Comparison

| model | encoding | horizon | city | RMSE | MAE | R2 |
| --- | --- | --- | --- | --- | --- | --- |
| Persistence Baseline | none | target_24h | OVERALL | 21.58 | 15.59 | 0.596 |
| Ridge Regression | one_hot | target_24h | OVERALL | 22.07 | 18.2 | 0.577 |
| XGBoost | one_hot | target_24h | OVERALL | 23.77 | 19.1 | 0.509 |
| XGBoost | integer | target_24h | OVERALL | 24.24 | 19.53 | 0.49 |
| Random Forest | integer | target_24h | OVERALL | 26.59 | 21.69 | 0.386 |
| Random Forest | one_hot | target_24h | OVERALL | 26.62 | 21.73 | 0.384 |
| Neural Network (MLP) | one_hot | target_24h | OVERALL | 72.91 | 61.21 | -3.617 |
| Persistence Baseline | none | target_48h | OVERALL | 27.79 | 21.88 | 0.351 |
| XGBoost | one_hot | target_48h | OVERALL | 30.5 | 25.27 | 0.218 |
| XGBoost | integer | target_48h | OVERALL | 31.43 | 26.1 | 0.17 |
| Ridge Regression | one_hot | target_48h | OVERALL | 33.19 | 27.77 | 0.074 |
| Random Forest | one_hot | target_48h | OVERALL | 33.24 | 28.03 | 0.071 |
| Random Forest | integer | target_48h | OVERALL | 33.43 | 28.22 | 0.061 |
| Neural Network (MLP) | one_hot | target_48h | OVERALL | 43.13 | 34.38 | -0.564 |
| Persistence Baseline | none | target_72h | OVERALL | 27.51 | 21.76 | 0.376 |
| Random Forest | integer | target_72h | OVERALL | 31.41 | 26.94 | 0.186 |
| XGBoost | one_hot | target_72h | OVERALL | 32.32 | 27.41 | 0.138 |
| Random Forest | one_hot | target_72h | OVERALL | 32.34 | 27.36 | 0.137 |
| XGBoost | integer | target_72h | OVERALL | 32.94 | 27.97 | 0.105 |
| Ridge Regression | one_hot | target_72h | OVERALL | 37.68 | 31.89 | -0.171 |
| Neural Network (MLP) | one_hot | target_72h | OVERALL | 66.38 | 55.07 | -2.635 |

## Per-City Detailed Breakdown

| model | encoding | horizon | city | RMSE | MAE | R2 |
| --- | --- | --- | --- | --- | --- | --- |
| Persistence Baseline | none | target_24h | OVERALL | 21.58 | 15.59 | 0.596 |
| Persistence Baseline | none | target_24h | Faisalabad | 22.97 | 17.71 | 0.064 |
| Persistence Baseline | none | target_24h | Gujranwala | 22.56 | 16.91 | -1.007 |
| Persistence Baseline | none | target_24h | Islamabad | 25.25 | 18.74 | -0.547 |
| Persistence Baseline | none | target_24h | Karachi | 7.72 | 6.21 | -0.169 |
| Persistence Baseline | none | target_24h | Lahore | 25.49 | 20.19 | -0.112 |
| Persistence Baseline | none | target_24h | Multan | 18.79 | 12.03 | 0.035 |
| Persistence Baseline | none | target_24h | Peshawar | 18.66 | 14.07 | -0.17 |
| Persistence Baseline | none | target_24h | Rawalpindi | 25.29 | 18.83 | -0.556 |
| Ridge Regression | one_hot | target_24h | OVERALL | 22.07 | 18.2 | 0.577 |
| Ridge Regression | one_hot | target_24h | Faisalabad | 24.08 | 19.74 | -0.028 |
| Ridge Regression | one_hot | target_24h | Gujranwala | 20.55 | 17.26 | -0.665 |
| Ridge Regression | one_hot | target_24h | Islamabad | 26.19 | 23.41 | -0.665 |
| Ridge Regression | one_hot | target_24h | Karachi | 10.47 | 8.23 | -1.15 |
| Ridge Regression | one_hot | target_24h | Lahore | 24.51 | 20.6 | -0.028 |
| Ridge Regression | one_hot | target_24h | Multan | 18.66 | 14.07 | 0.049 |
| Ridge Regression | one_hot | target_24h | Peshawar | 21.58 | 18.95 | -0.565 |
| Ridge Regression | one_hot | target_24h | Rawalpindi | 26.19 | 23.35 | -0.669 |
| XGBoost | one_hot | target_24h | OVERALL | 23.77 | 19.1 | 0.509 |
| XGBoost | one_hot | target_24h | Faisalabad | 25.21 | 19.84 | -0.127 |
| XGBoost | one_hot | target_24h | Gujranwala | 26.8 | 22.64 | -1.832 |
| XGBoost | one_hot | target_24h | Islamabad | 27.05 | 23.98 | -0.776 |
| XGBoost | one_hot | target_24h | Karachi | 7.53 | 6.57 | -0.113 |
| XGBoost | one_hot | target_24h | Lahore | 26.06 | 22.1 | -0.162 |
| XGBoost | one_hot | target_24h | Multan | 19.5 | 12.15 | -0.039 |
| XGBoost | one_hot | target_24h | Peshawar | 24.33 | 21.71 | -0.989 |
| XGBoost | one_hot | target_24h | Rawalpindi | 26.98 | 23.83 | -0.77 |
| XGBoost | integer | target_24h | OVERALL | 24.24 | 19.53 | 0.49 |
| XGBoost | integer | target_24h | Faisalabad | 24.92 | 19.85 | -0.101 |
| XGBoost | integer | target_24h | Gujranwala | 27.63 | 23.57 | -2.01 |
| XGBoost | integer | target_24h | Islamabad | 28.2 | 25.06 | -0.931 |
| XGBoost | integer | target_24h | Karachi | 7.25 | 6.3 | -0.032 |
| XGBoost | integer | target_24h | Lahore | 25.46 | 21.36 | -0.109 |
| XGBoost | integer | target_24h | Multan | 19.53 | 12.35 | -0.042 |
| XGBoost | integer | target_24h | Peshawar | 25.44 | 22.84 | -1.174 |
| XGBoost | integer | target_24h | Rawalpindi | 28.14 | 24.91 | -0.926 |
| Random Forest | one_hot | target_24h | OVERALL | 26.62 | 21.73 | 0.384 |
| Random Forest | one_hot | target_24h | Faisalabad | 26.78 | 21.32 | -0.272 |
| Random Forest | one_hot | target_24h | Gujranwala | 32.34 | 27.65 | -3.125 |
| Random Forest | one_hot | target_24h | Islamabad | 29.9 | 26.86 | -1.17 |
| Random Forest | one_hot | target_24h | Karachi | 8.11 | 7.14 | -0.29 |
| Random Forest | one_hot | target_24h | Lahore | 27.69 | 23.7 | -0.312 |
| Random Forest | one_hot | target_24h | Multan | 21.3 | 14.8 | -0.24 |
| Random Forest | one_hot | target_24h | Peshawar | 28.87 | 25.62 | -1.801 |
| Random Forest | one_hot | target_24h | Rawalpindi | 29.87 | 26.74 | -1.17 |
| Random Forest | integer | target_24h | OVERALL | 26.59 | 21.69 | 0.386 |
| Random Forest | integer | target_24h | Faisalabad | 26.76 | 21.35 | -0.27 |
| Random Forest | integer | target_24h | Gujranwala | 32.38 | 27.66 | -3.134 |
| Random Forest | integer | target_24h | Islamabad | 29.91 | 26.86 | -1.171 |
| Random Forest | integer | target_24h | Karachi | 8.05 | 7.07 | -0.272 |
| Random Forest | integer | target_24h | Lahore | 27.45 | 23.5 | -0.29 |
| Random Forest | integer | target_24h | Multan | 21.3 | 14.81 | -0.239 |
| Random Forest | integer | target_24h | Peshawar | 28.83 | 25.58 | -1.792 |
| Random Forest | integer | target_24h | Rawalpindi | 29.87 | 26.73 | -1.17 |
| Neural Network (MLP) | one_hot | target_24h | OVERALL | 72.91 | 61.21 | -3.617 |
| Neural Network (MLP) | one_hot | target_24h | Faisalabad | 56.09 | 44.34 | -4.578 |
| Neural Network (MLP) | one_hot | target_24h | Gujranwala | 75.79 | 63.83 | -21.655 |
| Neural Network (MLP) | one_hot | target_24h | Islamabad | 100.94 | 96.59 | -23.729 |
| Neural Network (MLP) | one_hot | target_24h | Karachi | 15.85 | 12.8 | -3.924 |
| Neural Network (MLP) | one_hot | target_24h | Lahore | 72.61 | 60.74 | -8.022 |
| Neural Network (MLP) | one_hot | target_24h | Multan | 58.16 | 50.96 | -8.242 |
| Neural Network (MLP) | one_hot | target_24h | Peshawar | 66.41 | 64.05 | -13.816 |
| Neural Network (MLP) | one_hot | target_24h | Rawalpindi | 100.65 | 96.33 | -23.636 |
| Persistence Baseline | none | target_48h | OVERALL | 27.79 | 21.88 | 0.351 |
| Persistence Baseline | none | target_48h | Faisalabad | 32.05 | 24.57 | -0.793 |
| Persistence Baseline | none | target_48h | Gujranwala | 27.88 | 22.48 | -2.153 |
| Persistence Baseline | none | target_48h | Islamabad | 30.11 | 24.57 | -2.619 |
| Persistence Baseline | none | target_48h | Karachi | 10.8 | 8.9 | -1.839 |
| Persistence Baseline | none | target_48h | Lahore | 34.54 | 29.68 | -1.05 |
| Persistence Baseline | none | target_48h | Multan | 24.71 | 19.15 | -0.67 |
| Persistence Baseline | none | target_48h | Peshawar | 25.3 | 21.16 | -1.098 |
| Persistence Baseline | none | target_48h | Rawalpindi | 30.09 | 24.48 | -2.698 |
| Ridge Regression | one_hot | target_48h | OVERALL | 33.19 | 27.77 | 0.074 |
| Ridge Regression | one_hot | target_48h | Faisalabad | 34.08 | 28.2 | -1.027 |
| Ridge Regression | one_hot | target_48h | Gujranwala | 29.46 | 25.51 | -2.521 |
| Ridge Regression | one_hot | target_48h | Islamabad | 40.64 | 38.31 | -5.594 |
| Ridge Regression | one_hot | target_48h | Karachi | 12.13 | 9.33 | -2.582 |
| Ridge Regression | one_hot | target_48h | Lahore | 35.63 | 28.49 | -1.181 |
| Ridge Regression | one_hot | target_48h | Multan | 25.11 | 19.48 | -0.724 |
| Ridge Regression | one_hot | target_48h | Peshawar | 38.07 | 34.78 | -3.749 |
| Ridge Regression | one_hot | target_48h | Rawalpindi | 40.41 | 38.07 | -5.67 |
| XGBoost | one_hot | target_48h | OVERALL | 30.5 | 25.27 | 0.218 |
| XGBoost | one_hot | target_48h | Faisalabad | 33.56 | 27.19 | -0.966 |
| XGBoost | one_hot | target_48h | Gujranwala | 34.74 | 29.0 | -3.895 |
| XGBoost | one_hot | target_48h | Islamabad | 32.59 | 30.75 | -3.239 |
| XGBoost | one_hot | target_48h | Karachi | 9.93 | 8.48 | -1.398 |
| XGBoost | one_hot | target_48h | Lahore | 34.44 | 27.66 | -1.038 |
| XGBoost | one_hot | target_48h | Multan | 24.02 | 17.42 | -0.578 |
| XGBoost | one_hot | target_48h | Peshawar | 33.75 | 31.23 | -2.733 |
| XGBoost | one_hot | target_48h | Rawalpindi | 32.33 | 30.42 | -3.27 |
| XGBoost | integer | target_48h | OVERALL | 31.43 | 26.1 | 0.17 |
| XGBoost | integer | target_48h | Faisalabad | 32.8 | 26.55 | -0.878 |
| XGBoost | integer | target_48h | Gujranwala | 36.04 | 30.56 | -4.268 |
| XGBoost | integer | target_48h | Islamabad | 34.97 | 33.12 | -3.88 |
| XGBoost | integer | target_48h | Karachi | 10.01 | 8.58 | -1.436 |
| XGBoost | integer | target_48h | Lahore | 33.79 | 26.72 | -0.962 |
| XGBoost | integer | target_48h | Multan | 24.71 | 17.71 | -0.669 |
| XGBoost | integer | target_48h | Peshawar | 35.59 | 32.98 | -3.15 |
| XGBoost | integer | target_48h | Rawalpindi | 34.48 | 32.55 | -3.856 |
| Random Forest | one_hot | target_48h | OVERALL | 33.24 | 28.03 | 0.071 |
| Random Forest | one_hot | target_48h | Faisalabad | 32.75 | 28.52 | -0.873 |
| Random Forest | one_hot | target_48h | Gujranwala | 36.92 | 32.05 | -4.529 |
| Random Forest | one_hot | target_48h | Islamabad | 39.01 | 35.62 | -5.075 |
| Random Forest | one_hot | target_48h | Karachi | 12.62 | 11.11 | -2.877 |
| Random Forest | one_hot | target_48h | Lahore | 30.6 | 25.43 | -0.609 |
| Random Forest | one_hot | target_48h | Multan | 23.13 | 18.95 | -0.463 |
| Random Forest | one_hot | target_48h | Peshawar | 41.93 | 37.36 | -4.763 |
| Random Forest | one_hot | target_48h | Rawalpindi | 38.63 | 35.24 | -5.095 |
| Random Forest | integer | target_48h | OVERALL | 33.43 | 28.22 | 0.061 |
| Random Forest | integer | target_48h | Faisalabad | 32.4 | 28.16 | -0.832 |
| Random Forest | integer | target_48h | Gujranwala | 37.06 | 32.24 | -4.572 |
| Random Forest | integer | target_48h | Islamabad | 39.21 | 35.84 | -5.135 |
| Random Forest | integer | target_48h | Karachi | 13.26 | 11.69 | -3.277 |
| Random Forest | integer | target_48h | Lahore | 31.1 | 25.68 | -0.662 |
| Random Forest | integer | target_48h | Multan | 23.24 | 19.01 | -0.478 |
| Random Forest | integer | target_48h | Peshawar | 42.18 | 37.6 | -4.831 |
| Random Forest | integer | target_48h | Rawalpindi | 38.94 | 35.56 | -5.193 |
| Neural Network (MLP) | one_hot | target_48h | OVERALL | 43.13 | 34.38 | -0.564 |
| Neural Network (MLP) | one_hot | target_48h | Faisalabad | 54.01 | 46.25 | -4.091 |
| Neural Network (MLP) | one_hot | target_48h | Gujranwala | 56.19 | 48.02 | -11.804 |
| Neural Network (MLP) | one_hot | target_48h | Islamabad | 35.5 | 28.15 | -4.03 |
| Neural Network (MLP) | one_hot | target_48h | Karachi | 12.07 | 10.48 | -2.546 |
| Neural Network (MLP) | one_hot | target_48h | Lahore | 59.6 | 51.42 | -5.103 |
| Neural Network (MLP) | one_hot | target_48h | Multan | 34.73 | 31.01 | -2.299 |
| Neural Network (MLP) | one_hot | target_48h | Peshawar | 36.75 | 30.77 | -3.427 |
| Neural Network (MLP) | one_hot | target_48h | Rawalpindi | 36.0 | 28.91 | -4.293 |
| Persistence Baseline | none | target_72h | OVERALL | 27.51 | 21.76 | 0.376 |
| Persistence Baseline | none | target_72h | Faisalabad | 33.41 | 26.87 | -1.015 |
| Persistence Baseline | none | target_72h | Gujranwala | 24.34 | 20.16 | -1.299 |
| Persistence Baseline | none | target_72h | Islamabad | 27.25 | 21.41 | -2.213 |
| Persistence Baseline | none | target_72h | Karachi | 11.31 | 9.2 | -2.142 |
| Persistence Baseline | none | target_72h | Lahore | 36.03 | 29.92 | -1.373 |
| Persistence Baseline | none | target_72h | Multan | 28.77 | 25.25 | -1.452 |
| Persistence Baseline | none | target_72h | Peshawar | 24.7 | 20.2 | -0.893 |
| Persistence Baseline | none | target_72h | Rawalpindi | 27.15 | 21.07 | -2.251 |
| Ridge Regression | one_hot | target_72h | OVERALL | 37.68 | 31.89 | -0.171 |
| Ridge Regression | one_hot | target_72h | Faisalabad | 40.56 | 34.22 | -1.969 |
| Ridge Regression | one_hot | target_72h | Gujranwala | 34.65 | 31.01 | -3.66 |
| Ridge Regression | one_hot | target_72h | Islamabad | 45.01 | 42.59 | -7.762 |
| Ridge Regression | one_hot | target_72h | Karachi | 10.46 | 8.38 | -1.69 |
| Ridge Regression | one_hot | target_72h | Lahore | 41.49 | 34.26 | -2.146 |
| Ridge Regression | one_hot | target_72h | Multan | 26.03 | 21.36 | -1.008 |
| Ridge Regression | one_hot | target_72h | Peshawar | 44.34 | 40.96 | -5.101 |
| Ridge Regression | one_hot | target_72h | Rawalpindi | 44.87 | 42.36 | -7.877 |
| XGBoost | one_hot | target_72h | OVERALL | 32.32 | 27.41 | 0.138 |
| XGBoost | one_hot | target_72h | Faisalabad | 34.55 | 27.85 | -1.154 |
| XGBoost | one_hot | target_72h | Gujranwala | 35.45 | 30.99 | -3.877 |
| XGBoost | one_hot | target_72h | Islamabad | 35.65 | 33.51 | -4.496 |
| XGBoost | one_hot | target_72h | Karachi | 13.09 | 10.93 | -3.206 |
| XGBoost | one_hot | target_72h | Lahore | 32.9 | 25.84 | -0.978 |
| XGBoost | one_hot | target_72h | Multan | 24.07 | 20.53 | -0.717 |
| XGBoost | one_hot | target_72h | Peshawar | 39.52 | 36.49 | -3.845 |
| XGBoost | one_hot | target_72h | Rawalpindi | 35.23 | 33.14 | -4.472 |
| XGBoost | integer | target_72h | OVERALL | 32.94 | 27.97 | 0.105 |
| XGBoost | integer | target_72h | Faisalabad | 33.67 | 27.52 | -1.046 |
| XGBoost | integer | target_72h | Gujranwala | 35.84 | 31.47 | -3.985 |
| XGBoost | integer | target_72h | Islamabad | 36.75 | 34.55 | -4.842 |
| XGBoost | integer | target_72h | Karachi | 13.48 | 11.39 | -3.461 |
| XGBoost | integer | target_72h | Lahore | 32.08 | 25.26 | -0.881 |
| XGBoost | integer | target_72h | Multan | 25.27 | 20.93 | -0.892 |
| XGBoost | integer | target_72h | Peshawar | 41.11 | 37.88 | -4.245 |
| XGBoost | integer | target_72h | Rawalpindi | 37.0 | 34.77 | -5.038 |
| Random Forest | one_hot | target_72h | OVERALL | 32.34 | 27.36 | 0.137 |
| Random Forest | one_hot | target_72h | Faisalabad | 34.6 | 27.99 | -1.16 |
| Random Forest | one_hot | target_72h | Gujranwala | 38.23 | 30.93 | -4.672 |
| Random Forest | one_hot | target_72h | Islamabad | 33.39 | 31.04 | -3.824 |
| Random Forest | one_hot | target_72h | Karachi | 19.11 | 15.99 | -7.968 |
| Random Forest | one_hot | target_72h | Lahore | 33.05 | 26.0 | -0.996 |
| Random Forest | one_hot | target_72h | Multan | 24.87 | 21.83 | -0.833 |
| Random Forest | one_hot | target_72h | Peshawar | 37.77 | 34.42 | -3.427 |
| Random Forest | one_hot | target_72h | Rawalpindi | 33.02 | 30.67 | -3.808 |
| Random Forest | integer | target_72h | OVERALL | 31.41 | 26.94 | 0.186 |
| Random Forest | integer | target_72h | Faisalabad | 29.66 | 26.19 | -0.588 |
| Random Forest | integer | target_72h | Gujranwala | 33.58 | 26.77 | -3.375 |
| Random Forest | integer | target_72h | Islamabad | 34.0 | 31.56 | -3.999 |
| Random Forest | integer | target_72h | Karachi | 18.86 | 15.71 | -7.733 |
| Random Forest | integer | target_72h | Lahore | 32.14 | 25.95 | -0.888 |
| Random Forest | integer | target_72h | Multan | 26.46 | 22.75 | -1.075 |
| Random Forest | integer | target_72h | Peshawar | 38.95 | 35.5 | -3.707 |
| Random Forest | integer | target_72h | Rawalpindi | 33.54 | 31.12 | -3.961 |
| Neural Network (MLP) | one_hot | target_72h | OVERALL | 66.38 | 55.07 | -2.635 |
| Neural Network (MLP) | one_hot | target_72h | Faisalabad | 84.08 | 74.23 | -11.76 |
| Neural Network (MLP) | one_hot | target_72h | Gujranwala | 77.01 | 68.25 | -22.015 |
| Neural Network (MLP) | one_hot | target_72h | Islamabad | 70.53 | 64.57 | -20.518 |
| Neural Network (MLP) | one_hot | target_72h | Karachi | 15.13 | 12.61 | -4.623 |
| Neural Network (MLP) | one_hot | target_72h | Lahore | 69.87 | 58.58 | -7.922 |
| Neural Network (MLP) | one_hot | target_72h | Multan | 54.71 | 43.07 | -7.867 |
| Neural Network (MLP) | one_hot | target_72h | Peshawar | 60.28 | 51.61 | -10.276 |
| Neural Network (MLP) | one_hot | target_72h | Rawalpindi | 74.44 | 67.65 | -23.438 |
