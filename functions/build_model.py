from rdkit import Chem
import numpy as np
import pandas as pd
import math,joblib, sys, os.path, csv
from sklearn import datasets, svm
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, cohen_kappa_score, matthews_corrcoef
from sklearn.impute import SimpleImputer
import inout as io
import stats as st

def load_desc(path,inp,arg):
# Create a folder to save the model (model_name/model_name.pkl)
	print('\n-> Loading the descriptors')
	print('loaded from:\n'+path+'/'+inp)
	print('\n-> Loading the activity')
	print('loaded from:\n'+path+'/'+arg)
	x=np.loadtxt(path+'/'+inp)
	y=np.loadtxt(path+'/'+arg)
#	x = np.array(x, dtype='float64')
#	y = np.array(y, dtype='float64')

	return x,y

def build_model(x,y,verb,path,nproc):
# Variable with % of the total database that is used as test
	test_size=.2
	seed=42
# Split the descriptors in train and test sets
	print('\n-> Splitting the data into train and test sets')
	x_tr, x_ts, y_tr, y_ts = train_test_split(x, y, test_size=test_size, random_state=seed)
	if verb:
# Print the training set
		for i in range(int((1-test_size)*len(y))):
			print(x_tr[i],x[i])
			for j in range(len(y)):
				if np.array_equal(x_tr[i], x[j]):
					print('Compound',j, 'is used as training')
# Print the training set
		for i in range(int(test_size*len(y))):
			print(x_ts[i],y[i]) 
			for j in range(len(y)): 
				if np.array_equal(x_ts[i], x[j]): 
					print('\nCompound',j, 'is used as test') 
	print('\n-> Performing 5-fold cross-validation\n')
# Perform and save the KFold 
	cv = StratifiedKFold(n_splits=5, random_state=seed)
	if verb:
# print out ids of folds
		for i, (train_index, test_index) in enumerate(cv.split(x_tr, y_tr)): 
			print("\nFold_" + str(i+1)) 
			print("TRAIN:", train_index) 
			print("TEST:", test_index)
# Call SVM model. It needs: cv and all the descriptors divided into
# training and test sets
	svm=st.svm(cv,x_tr,x_ts,y_tr,y_ts,nproc,verb)	
	evaluate(svm,x_ts,y_ts,path,'SVM',verb)
# it is a good idea to save it for future use
#joblib.dump(scale, "logBB_scale.pkl", compress=3)
# Call RF model. It needs: cv and all the descriptors divided into
# training and test sets
	rf=st.rf(cv,x_tr,x_ts,y_tr,y_ts,nproc,verb)	
	evaluate(rf,x_ts,y_ts,path,'RF',verb)

# Call GBM model. It needs: cv and all the descriptors divided into
# training and test sets
	gbm=st.gbm(cv,x_tr,x_ts,y_tr,y_ts,nproc,verb)	
	evaluate(gbm,x_ts,y_ts,path,'GBM',verb)
# Evaluate consensus model
	pred_c = 1 * (((rf.predict(x_ts)+svm.predict(x_ts)+gbm.predict(x_ts)) / 3) >= 0.5)
	print(pred_c)
# calc statistics
	print("Accuracy = ", accuracy_score(y_ts, pred_c))
	print("MCC = ", matthews_corrcoef(y_ts, pred_c))
	print("Kappa = ", cohen_kappa_score(y_ts, pred_c))
	
def evaluate(m,x_ts,y_ts,path,mess,verb):
# Evaluates the quality of the model by checking how good it predicts the
# test set (x_ts and y_ts)
#
# Predict test set
	predict = m.predict(x_ts)
#
# Calculate ratio (0-1) of correctly predicted compounds
	print('  Statistics of the model')
	acc_sc = accuracy_score(y_ts, predict)
	print('Accuracy: ',acc_sc)
#
# The MCC is in essence a correlation coefficient value between -1 and +1.
# A coefficient of +1 represents a perfect prediction, 0 an average random
# prediction and -1 an inverse prediction. The statistic is also known as
# the phi coefficient
	print('matthews_corrcoef: ', matthews_corrcoef(y_ts, predict))
#
# kappa = (p_0 - p_e)/(1 - p_e)
# where po is the relative observed agreement among raters (identical to
# accuracy) and pe is the hypothetical probability of chance agreement (see
# wikipedia for more detailed explanation)
	print('cohen_kappa_score: ',cohen_kappa_score(y_ts, predict))
# Save the model to folder <path>/<name>, where <name> is defined below
# (see function 'save')
	save(m,acc_sc,mess,path)
# if the model includes several ones like RF models or consensus models (or for probabilistic models)
# we can calculate consistency of predictions amongs those models and use it for estimation of applicability domain
	print('\n-> Test set applicability domain')
	pred_prob = m.predict_proba(x_ts)
# setup threshold
	threshold = 0.8
# calc maximum predicted probability for each row (compound) and compare to the threshold
	da = np.amax(pred_prob, axis=1) > threshold
	if verb:
# probablity
		print('  Predicted probability')
		print(pred_prob)
		print('  Threshold =',threshold)
		print('  Comparison between:')
		print(' maximum predicted probability for each row and compare to threshold')
		print(da)
# calc statistics
	print('accuracy_score: ',accuracy_score(np.asarray(y_ts)[da], predict[da]))
	print('matthews_corrcoef: ',matthews_corrcoef(np.asarray(y_ts)[da], predict[da]))
	print('cohen_kappa_score: ',cohen_kappa_score(np.asarray(y_ts)[da], predict[da]))
	print('Coverage: ',sum(da) / len(da))

# FUNCTION: save the model
# m
# acc_sc: accuracy of the model (from 'accuracy_score' variable rounded to
# mess: message (to specifiy in the name which model it is (RF, SVM...)
# 2 decimal places), to not replace different models
# path: path from <input> where all files with descriptors are contained
def save(m,acc_sc,mess,path):
	model_name= path+'/'+mess+'_'+str(round(acc_sc,2))+'.pkl'
	if os.path.isfile(model_name):
		print('ERROR: model with the same name exists.')
		print('Please, delete/rename the .pkl file and rerun the code')
		sys.exit()
	else:
		joblib.dump(m,model_name, compress=3)
		print('-> Model saved:', model_name)

#
# FUNCTION: predict dataset
# arg: model (.pkl file)
# path: path to the descriptors file. The code gets it from <input>
# inp: path to the descriptors file <input>
# d: .csv file with all data of the prediction dataset (ID,Compound name,
# SMILES, CAS)
#
def predict(arg,path,inp,clean_descs,csv_file):
# <arg>: filename of the model. Must be in <path>+<inp>
# <path>: path to the .csv file with the descriptors
# <inp>: .csv file with the descriptors. <path> and <inp> are taken from
# <input> (main option when running the code)
# <clean_descs>: DataFrame with clean descriptor values, the same that have been
# used to build the model
# <csv_file>: the .csv file loaded (<inp> file)
# Model is loaded
	m = joblib.load(path+'/'+arg)
# Evaluate applicability domain
	pred_prob = m.predict_proba(clean_descs)
# Define a threshold for until which point the molecule is included in the
# applicability domain
	th=0.8
	print('\n-> Applying applicability domain to the target molecules (threshold =',th,')')
	da = np.amax(pred_prob, axis=1) > th
# Predict test set
	print('\n-> Applying model',arg,'to predict',inp)
	predict = m.predict(clean_descs)
	print('\n-> .csv file with prediction data loaded from:',path+'/'+inp)
#
# FUNCTION: prints prediction
# Explanation and function in inout.py file
	io.print_csv(csv_file,predict,da,path,inp)
	 
	return predict
