#pip install torch torchvision matplotlib pillow

#-------------Import Necessary Libraries---------------

import torch
import torch.nn as nn
import torch.optim as optim
import torchvision.transforms as transforms
import torchvision.models as models
from PIL import Image
import matplotlib.pyplot as plt
import copy

#-------------Set Device--------------------------

device= torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device :", device)

# ----------- Image Loading-----------------------

def load_image(path, max_size=400):
    image= Image.open(path).convert("RGB")
    size= max(image.size)
    if size > max_size:
        size = max_size
        in_transform =transforms.Compose([transforms.Resize((size,size)),transforms.ToTensor(),
                                          transforms.Lambda(lambda x: x[:3, :, :]),
                                          transforms.Normalize([0.485, 0.456, 0.406],
                                                               [0.229, 0.224, 0.225])])
        image = in_transform(image)[:3, :, :].unsqueeze(0)
        return image.to(device)
def im_convert(tensor):
    image=tensor.to("cpu").clone().detach()
    image=image.squeeze(0)
    image= image * torch.tensor([0.229, 0.224, 0.225]).view(3,1,1) + torch.tensor([0.485, 0.456, 0.406]).view(3,1,1)
    image=image.clamp(0,1)
    return transforms.ToPILImage()(image)

#-------------Load Images----------------------------

content = load_image("content.jpg")
style = load_image("style.jpg")

#----------VGG19 Feature Extractor-------------------
vgg = models.vgg19(pretrained=True).features.to(device).eval()
# To Freeze model
for param in vgg.parameters():
    param.requires_grad = False

#-------Select VGG Layers----------------------------
def get_features(image, model, layers=None):
    if layers is None:
        layers = {
            '0' : 'conv1_1',
            '5' : 'conv2_1',
            '10': 'conv3_1',
            '19': 'conv4_1',
            '21': 'conv4_2',     #content layer
            '28': 'conv5_1'
        }
    features = {}
    x = image
    for name, layer in model._modules.items():
        x= layer(x)
        if name in layers:
            features[layers[name]] = x
    return features

#--------GRAM MATRIX-----------------------
def gram_matrix(tensor):
    _, d, h, w = tensor.size()
    tensor = tensor.view(d, h*w)
    gram = torch.mm(tensor, tensor.t())
    return gram
 #------Get Features----------------------
content_features = get_features(content, vgg)
style_features = get_features(style ,vgg)
style_grams = {layer: gram_matrix(style_features[layer]) for layer in style_features}

#--------------Initial Target--------------------
target = content.clone().requires_grad_(True).to(device)

#-------------Style Weights----------------------
style_weights = {
    'conv1_1' : 1.0,
    'conv2_1' : 0.75,
    'conv3_1' : 0.2,
    'conv4_1' : 0.2,
    'conv5_1' : 0.2 }
#----------Loss Weights -----------------------
content_weight = 1e4
style_weight = 1e2

#-----Optimizer-----------------
optimizer = optim.Adam([target], lr=0.003)

#---------Training---------
epochs =5000
for i in range(1,epochs+1):
    target_features = get_features(target, vgg)
    content_loss = torch.mean((target_features['conv4_2'] - content_features['conv4_2'])**2)
    
    style_loss = 0
    for layer in style_weights:
        target_feature = target_features[layer]
        target_gram = gram_matrix(target_feature)
        style_gram = style_grams[layer]
        layer_style_loss = style_weights[layer] * torch.mean((target_gram - style_gram)**2)
        b, d, h, w =target_feature.shape
        style_loss += layer_style_loss / (d * h *w)

    total_loss= content_weight * content_loss + style_weight * style_loss

    optimizer.zero_grad()
    total_loss.backward()
    optimizer.step()

    if i % 50 == 0 :
        print(f"Epoch {i}/{epochs}, Total loss: {total_loss.item():.4f}")

#-------Display Result-----------------
plt.imshow(im_convert(target))
plt.title("Stylized Output")
plt.axis("off")
#to save:
im_convert(target).save("stylized_output.png")
