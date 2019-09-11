import torch
from torch import nn


class DecoderBlock(nn.Module):
    def __init__(self,
                 in_channels=768,
                 n_filters=256,
                 kernel_size=4,
                 nonlinearity=nn.ReLU):
        super().__init__()

        if kernel_size == 3:
            conv_stride = 1
        elif kernel_size == 1:
            conv_stride = 1
        elif kernel_size == 4:
            conv_stride = 2

        self.decoder = nn.Sequential(
            # B, C, L -> B, C/4, L
            nn.Conv1d(in_channels,
                      in_channels // 4,
                      3,
                      padding=1),
            nn.BatchNorm1d(in_channels // 4),
            nonlinearity(inplace=True),
            # B, C/4, L -> B, C/4, L
            nn.ConvTranspose1d(in_channels // 4,
                               in_channels // 4,
                               kernel_size,
                               stride=conv_stride,
                               padding=1),
            nn.BatchNorm1d(in_channels // 4),
            nonlinearity(inplace=True),
            # B, C/4, L -> B, C, L
            nn.Conv1d(in_channels // 4,
                      n_filters,
                      3,
                      padding=1),
            nn.BatchNorm1d(n_filters),
            nonlinearity(inplace=True)
        )

    def forward(self, x):
        return self.decoder(x)


class DenoiseLoss(nn.Module):
    def __init__(self):
        super(DenoiseLoss, self).__init__()
        self.mse_loss = nn.MSELoss(reduction='sum')
        self.bce_loss = nn.BCEWithLogitsLoss(reduction='sum')

    def forward(self, output, target):
        batch_size = target.size(0)
        sequence_length = target.size(2)
        # print(output.shape, target.shape)
        mse_loss = self.mse_loss(output, target)
        bce_loss = self.bce_loss(output, target)
        return (mse_loss + bce_loss) / batch_size / sequence_length


class MaskSimilarity(nn.Module):
    def __init__(self,
                 thresholds=[0.05, 0.1, 0.15]):
        super().__init__()
        self.thresholds = thresholds

    def forward(self, outputs, targets):
        assert outputs.size() == targets.size()

        dice_output = nn.functional.sigmoid(outputs)
        abs_diff = torch.abs(dice_output - targets.float())
        total = (abs_diff < 1.0).sum()

        metrics = []
        for threshold in self.thresholds:
            similar = (abs_diff < threshold).sum()
            metrics.append(similar / total)

        return sum(metrics) / len(metrics)


class TilingBlock(nn.Module):
    def __init__(self,
                 repeats=[2, 4, 8]):
        super().__init__()
        self.repeats = repeats

    @staticmethod
    def sound_tile(x,
                   n_tile=2,
                   batch_dim=0,
                   channel_dim=1):
        repeat_tup = (1, 1, n_tile)
        view_tup = (x.size(batch_dim), -1, x.size(channel_dim))
        transpose_axes = (1, 2)
        return x.transpose(*transpose_axes)\
                .repeat(*repeat_tup)\
                .view(*view_tup)\
                .transpose(*reversed(transpose_axes))

    def forward(self,
                spect,
                feature_maps):
        """
        ab
        cdef
        =>
        aabb
        cdef
        """
        assert len(feature_maps) == len(self.repeats)
        for fm in feature_maps:
            assert fm.size(0) == spect.size(0)

        repeat_fms = []
        for fm, repeat in zip(feature_maps, self.repeats):
            repeat_fms.append(self.sound_tile(fm,
                                              n_tile=repeat))

        # check that dimensions match
        for i in range(len(repeat_fms)):
            if repeat_fms[i].size() == spect.size():
                continue

            length_diff = spect.size(2) - repeat_fms[i].size(2)
            if length_diff < 0:
                repeat_fms[i] = repeat_fms[i][:,:,spect.size(2)]
            else:
                pad = torch.nn.ReplicationPad1d((length_diff//2,
                                                 length_diff - length_diff//2))
                repeat_fms[i] = pad(repeat_fms[i])

            assert repeat_fms[i].size() == spect.size()

        return repeat_fms
