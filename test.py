import torch
import torch.nn.functional as F
from torchmetrics.functional import structural_similarity_index_measure
from model import GammaUnet
from dataloader import create_dataloaders
import os
import numpy as np
from torchvision.utils import save_image
import lpips
from datetime import datetime

def calculate_psnr(img1, img2, max_pixel_value=1.0, gt_mean=True):
    """
    Calculate PSNR (Peak Signal-to-Noise Ratio) between two images.

    Args:
        img1 (torch.Tensor): First image (BxCxHxW)
        img2 (torch.Tensor): Second image (BxCxHxW)
        max_pixel_value (float): The maximum possible pixel value of the images. Default is 1.0.

    Returns:
        float: The PSNR value.
    """
    if gt_mean:
        img1_gray = img1.mean(axis=1)
        img2_gray = img2.mean(axis=1)
        
        mean_restored = img1_gray.mean()
        mean_target = img2_gray.mean()
        img1 = torch.clamp(img1 * (mean_target / mean_restored), 0, 1)
    
    mse = F.mse_loss(img1, img2, reduction='mean')
    if mse == 0:
        return float('inf')
    psnr = 20 * torch.log10(max_pixel_value / torch.sqrt(mse))
    return psnr.item()

def calculate_ssim(img1, img2, max_pixel_value=1.0, gt_mean=True):
    """
    Calculate SSIM (Structural Similarity Index) between two images.

    Args:
        img1 (torch.Tensor): First image (BxCxHxW)
        img2 (torch.Tensor): Second image (BxCxHxW)
        max_pixel_value (float): The maximum possible pixel value of the images. Default is 1.0.

    Returns:
        float: The SSIM value.
    """
    if gt_mean:
        img1_gray = img1.mean(axis=1, keepdim=True)
        img2_gray = img2.mean(axis=1, keepdim=True)
        
        mean_restored = img1_gray.mean()
        mean_target = img2_gray.mean()
        img1 = torch.clamp(img1 * (mean_target / mean_restored), 0, 1)

    ssim_val = structural_similarity_index_measure(img1, img2, data_range=max_pixel_value)
    return ssim_val.item()

def validate(model, dataloader, device, result_dir):
    model.eval()
    total_psnr = 0
    total_ssim = 0
    total_lpips = 0
    loss_fn = lpips.LPIPS(net='alex').to(device)
    with torch.no_grad():
        for idx, (low, high) in enumerate(dataloader):
            low, high = low.to(device), high.to(device)
            output = model(low)
            output = torch.clamp(output, 0, 1)

            # Save the output image
            save_image(output, os.path.join(result_dir, f'result_{idx}.png'))

            # Calculate PSNR
            psnr = calculate_psnr(output, high)
            total_psnr += psnr

            # Calculate SSIM
            ssim = calculate_ssim(output, high)
            total_ssim += ssim

            # Calculate LPIPS
            lpips_score = loss_fn.forward(high, output)
            total_lpips += lpips_score.item()

    avg_psnr = total_psnr / len(dataloader)
    avg_ssim = total_ssim / len(dataloader)
    avg_lpips = total_lpips / len(dataloader)
    return avg_psnr, avg_ssim, avg_lpips

def main():
    # Paths and device setup
    test_low = 'data/LOLv1/Test/input'
    test_high = 'data/LOLv1/Test/target'
    weights_path = '/content/drive/MyDrive/Gamma-Unet/best_model.pth'
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    dataset_name = test_low.split('/')[1]
    result_dir = '/content/drive/MyDrive/Gamma-Unet/results/testing/output'

    _, test_loader = create_dataloaders(None, None, test_low, test_high, crop_size=None, batch_size=1)
    print(f'Test loader: {len(test_loader)}')

    model = GammaUnet().to(device)
    model.load_state_dict(torch.load(weights_path, map_location=device))
    print(f'Model loaded from {weights_path}')

    avg_psnr, avg_ssim, avg_lpips = validate(model, test_loader, device, result_dir)
    print(f'Validation PSNR: {avg_psnr:.6f}, SSIM: {avg_ssim:.6f}, LPIPS: {avg_lpips:.6f}')

    # write log
    now = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    file_path = "/content/drive/MyDrive/Gamma-Unet/results/testing/metrics.md"
    file_exists = os.path.exists(file_path)

    with open(file_path, "a") as f:
        if not file_exists:
            f.write("| Timestemp | PSNR | SSIM | LPIPS |\n")
            f.write("|-----------|------|------|-------|\n")
        
        f.write(f"| {now} | {avg_psnr:.6f} | {avg_ssim:.6f} | {avg_lpips:.6f} |\n")

if __name__ == '__main__':
    main()
