#!/usr/bin/env python
# coding: utf-8

# # Final Project STAT 259: Single Cell Sequencing Analysis

# In[1]:


import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import sklearn.metrics as metrics
from sklearn.model_selection import train_test_split
from sklearn.model_selection import StratifiedKFold
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.preprocessing import StandardScaler
import keras
from keras import layers
from keras import regularizers
from keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau
from keras.models import save_model, load_model


# ## Read data

# In[2]:


def setup_data(name):
    """
    ...
    """
    file = f"data/{name}-counts.csv"
    counts = pd.read_csv(file)
    counts.rename(columns={'Unnamed: 0':'index'}, inplace=True)
    counts.set_index("index", inplace=True)
    counts = counts.T
    counts.insert(0, 'cell_label', name)
    return counts


# In[3]:


organs = [
    "Kidney",
    "Liver",
]


# In[4]:


assert len(organs) == 2


# ## Feature filter

# In[5]:


data = pd.DataFrame()
for organ in organs:
    data = data.append(setup_data(organ))
data.shape


# In[6]:


# Remove gene counts with zero variance
std = data.std(axis=0, numeric_only=True)
final_features = list(std[std != 0].index)
data = data[final_features + ["cell_label"]]
data.shape


# In[7]:


std = std[final_features]


# In[8]:


mu = data.groupby(data["cell_label"]).mean().T


# In[9]:


score = np.abs((mu[organs[0]] - mu[organs[1]])/std).sort_values(ascending=False)
score.head(20)


# In[10]:


# Choose subset of gene counts
num_genes = 1000
selected_features = list(score.iloc[:num_genes].index)
data = data[selected_features + ["cell_label"]]
data.shape


# ## Feature preprocessing

# In[11]:


data.iloc[:, :-1] = np.log(data.iloc[:,:-1] + 1)


# In[12]:


filepath = "processed_data/data.csv"
data.to_csv(filepath, index=True)


# # Lower-dimension representation of the cells

# In[13]:


data = pd.read_csv(filepath, index_col=0)


# In[14]:


data


# In[15]:


x = data.iloc[:, :-1]
y = data.iloc[:, -1]


# In[16]:


# One hot encoding of y labels
# Order chosen by proportions in sample and kept in y_labels
y_hot = pd.get_dummies(y)
y_labels = y_hot.mean(axis=0).sort_values(ascending=False).index
y_hot = y_hot[y_labels]
y_hot.head()


# In[17]:


# 80:20 split shuffling data
x_train, x_test, y_train, y_test = train_test_split(x, y_hot, test_size=0.2, random_state=42, shuffle=True, stratify=y)


# In[18]:


# Shape validation for x
x.shape, x_train.shape, x_test.shape


# In[19]:


# Shape validation for y
y.shape, y_train.shape, y_test.shape


# ## Autoencoder

# In[20]:


# Latent space of 32 dimensions
# 1 hidden layer for encoder and one for decoder
# L1 regularization used in fully connected layers
# Encoder will be defined later after training

encoding_dim = 32
input_dim = x.shape[1]

input_obj = keras.Input(shape=(input_dim,))
dropout1 = layers.Dropout(.2)(input_obj)
hidden1 = layers.Dense(128, activation='relu', 
                       activity_regularizer=regularizers.l1(10e-5))(dropout1)
dropout2 = layers.Dropout(.2)(hidden1)
encoded = layers.Dense(encoding_dim, activation='relu', 
                       activity_regularizer=regularizers.l1(10e-5))(dropout2)
dropout3 = layers.Dropout(.2)(encoded)
hidden2 = layers.Dense(128, activation='relu')(dropout3)
dropout4 = layers.Dropout(.2)(hidden2)
decoded = layers.Dense(input_dim, activation='sigmoid')(dropout4)

autoencoder = keras.Model(input_obj, decoded)
autoencoder.summary()


# In[21]:


# Configurations for improving training with the aim to reduce over-fitting 
# and also allow to seek for a lower bias model.
# Reference: https://stackoverflow.com/questions/48285129/saving-best-model-in-keras
earlyStopping = EarlyStopping(monitor='val_loss', patience=20, verbose=0, mode='min')
mcp_save = ModelCheckpoint('models/autoencoder_best.hdf5', save_best_only=True, monitor='val_loss', mode='min')
reduce_lr_loss = ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=10, verbose=0, min_delta=1e-4, mode='min')


# In[22]:


# Used MSE as loss
autoencoder.compile(optimizer='adam', loss='mean_squared_error')

autoencoder.fit(
    x_train, x_train,
    epochs=500,
    batch_size=256,
    shuffle=True,
    validation_data=(x_test, x_test),
    callbacks=[earlyStopping, mcp_save, reduce_lr_loss],
    verbose=0,
)


# In[23]:


# Load best
autoencoder = load_model('models/autoencoder_best.hdf5', compile=False)
autoencoder.compile(optimizer='adam', loss='mean_squared_error')


# In[24]:


# Evaluate autoencoder performance
autoencoder.evaluate(x_test, x_test)


# In[25]:


# Encoder
encoder_output = autoencoder.layers[4].output
encoder_input = autoencoder.input
encoder = keras.Model(encoder_input, encoder_output)
encoder.summary()


# In[26]:


# Save model
encoder.compile(optimizer='adam', loss='mean_squared_error')
save_model(encoder, 'models/encoder_best.hdf5', save_format='hdf5')


# In[27]:


# PCA
pca32 = PCA(n_components=32)
x_pca = pca32.fit_transform(x)


# In[28]:


# t-SNE
tsne2 = TSNE(n_components=2, learning_rate=200, init='random', method='exact')
x_tsne2 = tsne2.fit_transform(x_pca)


# In[29]:


# Encoder used to get input data's latent variables
x_encoded = encoder.predict(x)
x_encoded.shape


# In[30]:


# Encoder to 32 dim, then t-SNE to 2 dim
x_encoded_tsne2 = tsne2.fit_transform(x_encoded)


# In[31]:


# Plot 2D representations
ncols = 2
fig, ax = plt.subplots(1, ncols, figsize=(12, 6))

x_dict = {
    'PCA': x_pca[:, :2],
    #'t-SNE': x_tsne2,
    'Autoencoder to 32 dim,\nthen t-SNE to 2 dim': x_encoded_tsne2,
}

n = len(x_dict)

for i, (title, x_plot) in enumerate(x_dict.items()):

    col = i
    ax_i = ax[col]

    sns.scatterplot(
        x=x_plot[:,0], y=x_plot[:,1],
        hue=y,
        palette=sns.color_palette("hls", 2),
        legend="full",
        alpha=0.75,
        ax=ax_i)
    if i == n - 1:
        handles, labels = ax_i.get_legend_handles_labels()
    ax_i.get_legend().remove()
    ax_i.set_title(title)
    ax_i.set_xlabel('Component 1')
    if col == 0:
        ax_i.set_ylabel('Component 2')

fig.legend(handles, labels, bbox_to_anchor=(0.9, 0.4), loc='lower center', ncol=1)
fig.tight_layout()
fig.subplots_adjust(right=0.8)

plt.savefig('figures/projection.jpg', format='jpg')
plt.show()


# # Classifier

# ## Cross Validation

# In[32]:


def initilize_supervised_model(size):
    """
    - Loads trained encoder
    - Adds layers according to size given (size in ['small', 'larger'])
      for supervized learning set up (label prediction)
    - Returns supervised model with untrained added layers
      but first layers, coming from encoder, are trained already
    """

    assert size in ['small', 'larger']

    # Load encoder
    encoder_load = load_model('models/encoder_best.hdf5', compile=False)

    # Add layers
    encoder_output = encoder_load.layers[-1].output
    encoder_input = encoder_load.input
    if size == 'small':
        # Small model
        dropout = layers.Dropout(.2)(encoder_output)
        output = layers.Dense(2, activation='softmax')(dropout)
        nn_model = keras.Model(encoder_input, output)
    elif size == 'larger':
        # Larger model
        dropout_output1 = layers.Dropout(.2)(encoder_output)
        dense_output1 = layers.Dense(16, activation='relu')(dropout_output1)
        dropout_output2 = layers.Dropout(.2)(dense_output1)
        output = layers.Dense(2, activation='softmax')(dropout_output2)
        nn_model = keras.Model(encoder_input, output)

    # Fix encoder parameters to avoid overfitting
    idx_not_train = [1, 2, 3, 4]
    for i in idx_not_train:
        nn_model.layers[i].trainable = False

    nn_model.compile(optimizer='adam', loss='categorical_crossentropy')

    return nn_model


# In[33]:


# Small model quick validation
nn_small = initilize_supervised_model('small')
nn_small.summary()


# In[34]:


# Larger model quick validation
nn_larger = initilize_supervised_model('larger')
nn_larger.summary()


# In[35]:


# Call backs

# Early stopping
earlyStopping = EarlyStopping(
    monitor='val_loss', 
    patience=20, 
    verbose=0, 
    mode='min'
)

# Reduce learning rate on plateu
reduce_lr_loss = ReduceLROnPlateau(
    monitor='val_loss', 
    factor=0.5, 
    patience=10, 
    min_delta=1e-4, 
    mode='min',
    verbose=0,
)

# Save best model by validation loss
def mcp_save(size):
    return ModelCheckpoint(
      f"models/nn_{size}_best.hdf5", 
      save_best_only=True, 
      monitor='val_loss', 
      mode='min',
    )


# In[36]:


def compute_metrics(y_true, y_score, average='macro'):
    assert y_true.shape == y_score.shape
    y_ind_pred = np.argmax(y_score, axis=1)
    y_ind_true = np.argmax(y_true, axis=1)
    accuracy = metrics.accuracy_score(y_ind_true, y_ind_pred)
    precision = metrics.precision_score(y_ind_true, y_ind_pred, average=average)
    recall = metrics.recall_score(y_ind_true, y_ind_pred, average=average)
    f1 = metrics.f1_score(y_ind_true, y_ind_pred, average=average)
    roc_auc = metrics.roc_auc_score(y_true, y_score, average=average)
    return {
      "accuracy": accuracy,
      "precision": precision,
      "recall": recall,
      "f1": f1,
      "roc_auc": roc_auc,
    }


# In[37]:


# Cross validation

def nn_cross_validation(size, x, y, n_split=3):
    
    print(f"Cross-validation for size = {size}")

    # Stratified k-fold is used
    kfold = StratifiedKFold(n_split, shuffle=True, random_state=0)

    # Reset index
    xx = x.copy().reset_index(drop=True)
    yy = y.copy().reset_index(drop=True)
    yy_ind = np.argmax(yy.values, axis=1)

    rows = []
    for i, (train_index, test_index) in enumerate(kfold.split(xx, yy_ind)):

        # Split
        xx_train, xx_test = xx.loc[train_index], xx.loc[test_index]
        yy_train, yy_test = yy.loc[train_index], yy.loc[test_index]

        # Train and save model
        nn_model = initilize_supervised_model(size)
        nn_model.fit(
            xx_train, yy_train,
            epochs=500,
            batch_size=256,
            shuffle=True,
            validation_data=(xx_test, yy_test),
            callbacks=[earlyStopping, mcp_save(size), reduce_lr_loss],
            verbose=0,
        )

        # Load best model
        nn_model = load_model(f"models/nn_{size}_best.hdf5", compile=False)
        nn_model.compile(optimizer='adam', loss='categorical_crossentropy')

        # Assess performance
        loss = nn_model.evaluate(xx_test, yy_test, verbose=0)
        y_true = yy_test.values
        y_score = nn_model.predict(xx_test)
        row_dict = compute_metrics(y_true, y_score)
        row_dict['categorical_crossentropy'] = loss
        rows.append(row_dict)

    # Collect performance results
    results = pd.DataFrame.from_dict(rows, orient='columns')
    results = results.reset_index().rename(columns={'index': 'fold'})

    return results


# In[38]:


# Cross-validation results for small model: folds details
res_cv_small = nn_cross_validation("small", x_train, y_train)
res_cv_small


# In[39]:


# Cross-validation results for larger model: folds details
res_cv_larger = nn_cross_validation("larger", x_train, y_train)
res_cv_larger


# In[40]:


# Cross-validation aggregated results for both models
res_cv = pd.concat((res_cv_small.iloc[:,1:].mean(axis=0), res_cv_larger.iloc[:,1:].mean(axis=0)), axis=1).T.round(3)
res_cv.index = ['small', 'larger']
res_cv


# ## Test Performance

# In[41]:


def plot_roc_curve(name, y_true, y_score, indices, filename=None, extension=None):

    plt.figure(figsize=(10, 7))

    # Compute and plot fpr and tpr per selected labels/indices
    for ind in indices:
        y_score_ind = y_score[:, ind]
        y_true_ind = y_true == ind
        fpr, tpr, threshold = metrics.roc_curve(y_true_ind, y_score_ind)
        roc_auc = metrics.auc(fpr, tpr)
        plt.plot(fpr, tpr, label = f"{y_labels[ind]} (AUC={roc_auc:.2f})")

    if name:
        plt.title(f'Receiver Operating Characteristic {name}')
    plt.legend(loc='lower right')
    plt.plot([0, 1], [0, 1], 'r--')
    plt.xlim([0, 1])
    plt.ylim([0, 1])
    plt.ylabel('True Positive Rate')
    plt.xlabel('False Positive Rate')
    if filename:
        plt.savefig(f'figures/{filename}.{extension}', format=extension)
    plt.show()


# In[42]:


# Load last model trained in cross-validation
# Training needs a validation set so any fold model is OK
nn_small = load_model(f"models/nn_small_best.hdf5", compile=False)
nn_larger = load_model(f"models/nn_larger_best.hdf5", compile=False)
nn_small.compile(optimizer='adam', loss='categorical_crossentropy')
nn_larger.compile(optimizer='adam', loss='categorical_crossentropy')


# In[43]:


# Truth and predictions
y_true = y_test.values
y_true_ind = np.argmax(y_true, axis=1)
y_score_small = nn_small.predict(x_test)
y_score_larger = nn_larger.predict(x_test)


# In[44]:


# Confusion matrix
conf_matrix_small = metrics.confusion_matrix(y_true_ind, np.argmax(y_score_small, axis=1))
conf_matrix_larger = metrics.confusion_matrix(y_true_ind, np.argmax(y_score_larger, axis=1))


# In[45]:


def plot_confusion_matrix(name, conf_matrix, filename=None, extension=None):
    plt.figure(figsize=(8, 6))
    sns.heatmap(conf_matrix, cmap='Blues', annot=True, yticklabels=y_labels, xticklabels=y_labels)
    if name:
        plt.title(f"Confusion Matrix {name}")
    plt.xlabel("Predicted", fontsize=13)
    plt.ylabel("Actual", fontsize=13)
    if filename:
        plt.savefig(f'figures/{filename}.{extension}', format=extension)
    plt.show()


# In[46]:


# Confusion matrix small model
plot_confusion_matrix(None, 
                      conf_matrix_small, 
                      'confusion_matrix_small',
                      'jpg')


# In[47]:


# Confusion matrix larger model
plot_confusion_matrix(None, 
                      conf_matrix_larger, 
                      'confusion_matrix_larger',
                      'jpg')


# In[48]:


# Performance on test set
metrics_small = compute_metrics(y_true, y_score_small)
metrics_larger = compute_metrics(y_true, y_score_larger)
res = pd.DataFrame.from_dict([metrics_small, metrics_larger], 
                             orient='columns').round(3)
res.index = ['small', 'larger']
res


# In[49]:


# Plot ROC curve
prop_min=0.05
label_prop = y_hot.mean(axis=0).reindex(labels)
indices = [ind for ind in range(len(labels)) if label_prop.iloc[ind] >= prop_min]
display(label_prop)
print(f"Indices to plot: {indices}")


# In[50]:


# ROC curve small model
plot_roc_curve(
    None, 
    y_true_ind,
    y_score_small,
    indices,
    "roc_small",
    "jpg"
)


# In[51]:


# ROC curve larger model
plot_roc_curve(
    None, 
    y_true_ind,
    y_score_larger,
    indices,
    "roc_larger",
    "jpg"
)

